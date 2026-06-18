from __future__ import annotations

import logging
from datetime import datetime, timezone

from slack_sdk.models.blocks import (
    ActionsBlock,
    ButtonElement,
    ContextBlock,
    DividerBlock,
    HeaderBlock,
    MarkdownTextObject,
    SectionBlock,
)

from src.config import BOT_DISPLAY_NAME
from src.models import CaseAnalysis, RoutingDecision, SupportCase, Severity

logger = logging.getLogger(__name__)

SEVERITY_EMOJI = {
    Severity.SEV1: ":rotating_light:",
    Severity.SEV2: ":warning:",
    Severity.SEV3: ":large_blue_circle:",
    Severity.UNKNOWN: ":grey_question:",
}


def build_case_notification_blocks(
    case: SupportCase,
    analysis: CaseAnalysis,
    routing: RoutingDecision,
) -> list[dict]:
    emoji = SEVERITY_EMOJI.get(analysis.severity, ":bell:")
    request_labels = ", ".join(t.value for t in analysis.request_types)
    ai_tag = "AI" if analysis.used_ai else "Rules"
    mention = f"<@{routing.engineer.slack_user_id}>"

    blocks: list = [
        HeaderBlock(text=f"{emoji} {BOT_DISPLAY_NAME} — Action Required").to_dict(),
        SectionBlock(
            text=MarkdownTextObject(
                text=f"{mention} *New case assigned to you*\n*<{case.salesforce_url}|{case.case_number}>* — {case.subject}"
            )
        ).to_dict(),
        SectionBlock(
            fields=[
                MarkdownTextObject(text=f"*Severity:*\n{analysis.severity.value}"),
                MarkdownTextObject(text=f"*Priority:*\n{case.priority}"),
                MarkdownTextObject(text=f"*Account:*\n{case.account_name}"),
                MarkdownTextObject(text=f"*Product:*\n{case.product}"),
                MarkdownTextObject(text=f"*Region:*\n{case.region}"),
                MarkdownTextObject(text=f"*Request Type:*\n{request_labels}"),
            ]
        ).to_dict(),
        SectionBlock(text=MarkdownTextObject(text=f"*Summary:*\n{analysis.summary}")).to_dict(),
        ContextBlock(
            elements=[
                MarkdownTextObject(
                    text=(
                        f"Assigned to *{routing.engineer.name}* · "
                        f"Confidence: {analysis.confidence:.0%} · "
                        f"Analysis: {ai_tag} · "
                        f"Routing score: {routing.score:.0f}"
                    )
                )
            ]
        ).to_dict(),
        DividerBlock().to_dict(),
        ActionsBlock(
            elements=[
                ButtonElement(
                    text="View in Salesforce",
                    url=case.salesforce_url,
                    action_id="view_salesforce",
                ),
                ButtonElement(
                    text="Acknowledge",
                    action_id="acknowledge_case",
                    value=case.case_id,
                    style="primary",
                ),
                ButtonElement(
                    text="Reassign",
                    action_id="reassign_case",
                    value=case.case_id,
                ),
            ]
        ).to_dict(),
    ]

    return blocks


def build_case_notification_text(
    case: SupportCase,
    analysis: CaseAnalysis,
    routing: RoutingDecision,
) -> str:
    """Plain-text fallback — includes @mention so Slack triggers alert notifications."""
    mention = f"<@{routing.engineer.slack_user_id}>"
    return (
        f"{mention} {BOT_DISPLAY_NAME}: {analysis.severity.value} case {case.case_number} — "
        f"{case.subject}. Action required."
    )


def build_acknowledgment_message(case_number: str, engineer_name: str) -> str:
    return f":white_check_mark: *{engineer_name}* acknowledged case *{case_number}*."


def build_status_message(processed: int, notified: int, skipped: int) -> str:
    return (
        f":robot_face: *{BOT_DISPLAY_NAME} Status*\n"
        f"• Cases processed: {processed}\n"
        f"• Engineers notified: {notified}\n"
        f"• Skipped (non-actionable): {skipped}\n"
        f"• Last check: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
