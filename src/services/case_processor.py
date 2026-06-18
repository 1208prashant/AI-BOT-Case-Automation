from __future__ import annotations

import logging
from datetime import datetime, timezone

from slack_sdk import WebClient

from src.ai.analyzer import CaseAnalyzer
from src.models import NotificationRecord, SupportCase
from src.routing.router import EngineerRouter
from src.slack.notifications import build_case_notification_blocks, build_case_notification_text

logger = logging.getLogger(__name__)


class CaseProcessor:
    """End-to-end pipeline: analyze → route → notify."""

    def __init__(
        self,
        analyzer: CaseAnalyzer,
        router: EngineerRouter,
        slack_client: WebClient,
    ):
        self.analyzer = analyzer
        self.router = router
        self.slack_client = slack_client
        self._processed_case_ids: set[str] = set()

    def process(self, case: SupportCase) -> NotificationRecord | None:
        if case.case_id in self._processed_case_ids:
            logger.debug("Case %s already processed, skipping", case.case_id)
            return None

        self._processed_case_ids.add(case.case_id)
        logger.info("Processing case %s: %s", case.case_number, case.subject)

        analysis = self.analyzer.analyze(case)
        if not analysis.is_actionable:
            logger.info(
                "Case %s not actionable (severity=%s, types=%s)",
                case.case_number,
                analysis.severity.value,
                [t.value for t in analysis.request_types],
            )
            return None

        routing = self.router.route(case, analysis)
        if not routing:
            logger.warning("No engineer available for case %s", case.case_number)
            return None

        engineer = routing.engineer
        if not self._is_valid_slack_user_id(engineer.slack_user_id):
            logger.error(
                "Engineer %s has invalid Slack ID '%s'. "
                "Run: python scripts/list_slack_users.py — then update config/engineers.json",
                engineer.name,
                engineer.slack_user_id,
            )
            return None

        if not self._send_dm(case, analysis, routing):
            return None

        return NotificationRecord(
            case_id=case.case_id,
            engineer_id=engineer.id,
            slack_channel=engineer.slack_user_id,
            sent_at=datetime.now(timezone.utc),
            analysis=analysis,
        )

    @staticmethod
    def _is_valid_slack_user_id(user_id: str) -> bool:
        return bool(user_id) and user_id.startswith("U") and not user_id.startswith("U_REPLACE")

    def _send_dm(self, case: SupportCase, analysis, routing) -> bool:
        engineer = routing.engineer
        blocks = build_case_notification_blocks(case, analysis, routing)
        text = build_case_notification_text(case, analysis, routing)

        try:
            dm = self.slack_client.conversations_open(users=engineer.slack_user_id)
            channel_id = dm["channel"]["id"]

            self.slack_client.chat_postMessage(
                channel=channel_id,
                text=text,
                blocks=blocks,
            )
            logger.info("Sent DM to %s for case %s", engineer.name, case.case_number)
            return True
        except Exception as exc:
            slack_error = str(exc)
            if hasattr(exc, "response") and exc.response is not None:
                slack_error = exc.response.get("error", slack_error)
            logger.error(
                "Failed to send Slack DM to %s (id=%s): %s. "
                "Run: python scripts/list_slack_users.py to find valid user IDs.",
                engineer.name,
                engineer.slack_user_id,
                slack_error,
            )
            return False
