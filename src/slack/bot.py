from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from src.ai.analyzer import CaseAnalyzer
from src.config import BOT_DISPLAY_NAME, BOT_SLASH_PREFIX, Settings, load_settings
from src.models import NotificationRecord, SupportCase
from src.routing.router import EngineerLoadTracker, EngineerRouter
from src.salesforce.client import MockSalesforceClient, SalesforceClient
from src.services.case_processor import CaseProcessor
from src.slack.notifications import (
    build_acknowledgment_message,
    build_status_message,
)

logger = logging.getLogger(__name__)


class CaseAutomationBot:
    """Main application orchestrating Salesforce monitoring and Slack notifications."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self.app = App(
            token=self.settings.slack_bot_token,
            signing_secret=self.settings.slack_signing_secret,
        )
        self.load_tracker = EngineerLoadTracker(counts={})
        self.router = EngineerRouter(load_tracker=self.load_tracker)
        self.analyzer = CaseAnalyzer(
            openai_api_key=self.settings.openai_api_key,
            openai_model=self.settings.openai_model,
            notify_sev3=self.settings.notify_sev3,
        )
        self.processor = CaseProcessor(
            analyzer=self.analyzer,
            router=self.router,
            slack_client=self.app.client,
        )
        self.case_source = self._build_case_source()
        self.notification_history: list[NotificationRecord] = []
        self.stats = {"processed": 0, "notified": 0, "skipped": 0}
        self._poll_thread: threading.Thread | None = None
        self._stop_polling = threading.Event()

        self._register_slack_handlers()
        self.webhook_app = self._build_webhook_app()

    def _build_case_source(self):
        if self.settings.mock_salesforce:
            logger.info(
                "Running in MOCK Salesforce mode — cases auto-generate every %ss and trigger DMs",
                self.settings.mock_case_interval_seconds,
            )
            return MockSalesforceClient(interval_seconds=self.settings.mock_case_interval_seconds)

        return SalesforceClient(
            instance_url=self.settings.salesforce_instance_url,
            client_id=self.settings.salesforce_client_id,
            client_secret=self.settings.salesforce_client_secret,
            username=self.settings.salesforce_username,
            password=self.settings.salesforce_password,
            security_token=self.settings.salesforce_security_token,
        )

    def _register_slack_handlers(self) -> None:
        @self.app.command(f"/{BOT_SLASH_PREFIX}-status")
        def handle_status(ack, respond):
            ack()
            respond(build_status_message(**self.stats))

        @self.app.command(f"/{BOT_SLASH_PREFIX}-engineers")
        def handle_engineers(ack, respond):
            ack()
            lines = ["*Configured Engineers:*"]
            for eng in self.router.list_engineers():
                load = self.load_tracker.get(eng.id)
                status = "on-call" if eng.on_call else "off-call"
                lines.append(
                    f"• *{eng.name}* — skills: {', '.join(eng.skills[:4])}… "
                    f"· load: {load}/{eng.max_active_cases} · {status}"
                )
            respond("\n".join(lines))

        @self.app.command(f"/{BOT_SLASH_PREFIX}-simulate")
        def handle_simulate(ack, respond, command):
            ack()
            text = command.get("text", "").strip()
            case = self._parse_simulate_command(text, command["user_id"])
            if not case:
                respond(
                    f"Usage: `/{BOT_SLASH_PREFIX}-simulate Sev1 | Production outage | Platform A | AMER`\n"
                    f"Simulates a Salesforce case and runs the full {BOT_DISPLAY_NAME} pipeline."
                )
                return

            record = self.processor.process(case)
            if record:
                self._record_notification(record)
                respond(
                    f":rocket: Simulated case *{case.case_number}* routed to "
                    f"*{record.engineer_id}* (check your DMs if you're the assignee)."
                )
            else:
                respond(f"Case *{case.case_number}* was analyzed but deemed non-actionable.")

        @self.app.action("acknowledge_case")
        def handle_acknowledge(ack, body, client):
            ack()
            user_id = body["user"]["id"]
            case_id = body["actions"][0]["value"]
            engineer = self.router.get_engineer_by_slack_id(user_id)
            name = engineer.name if engineer else body["user"]["name"]
            case_number = next(
                (r.case_id for r in self.notification_history if r.case_id == case_id),
                case_id,
            )
            channel = body["channel"]["id"]
            client.chat_postMessage(
                channel=channel,
                text=build_acknowledgment_message(case_number, name),
            )

        @self.app.event("app_mention")
        def handle_mention(event, say):
            say(
                text=(
                    f":wave: I'm *{BOT_DISPLAY_NAME}* — your support case assistant.\n"
                    f"• `/{BOT_SLASH_PREFIX}-status` — pipeline stats\n"
                    f"• `/{BOT_SLASH_PREFIX}-engineers` — routing roster\n"
                    f"• `/{BOT_SLASH_PREFIX}-simulate` — test a case end-to-end"
                )
            )

    def _parse_simulate_command(self, text: str, user_id: str) -> SupportCase | None:
        if not text:
            return None

        parts = [part.strip() for part in text.split("|")]
        severity = parts[0] if parts else "Sev2"
        subject = parts[1] if len(parts) > 1 else "Simulated support case"
        product = parts[2] if len(parts) > 2 else "Platform A"
        region = parts[3] if len(parts) > 3 else "AMER"

        now = datetime.now(timezone.utc)
        case_id = f"SIM-{int(now.timestamp())}"

        return SupportCase(
            case_id=case_id,
            case_number=case_id,
            subject=f"{severity} — {subject}",
            description=f"Simulated case triggered by <@{user_id}>. {subject}",
            priority="Critical" if "1" in severity else "High",
            status="New",
            account_name="Simulated Account",
            contact_name="Test User",
            product=product,
            region=region,
            is_key_customer="key" in subject.lower(),
            created_at=now,
            salesforce_url="https://example.my.salesforce.com",
        )

    def _build_webhook_app(self) -> Flask:
        flask_app = Flask(__name__)

        @flask_app.route("/health", methods=["GET"])
        def health():
            return jsonify({"status": "ok", "service": "ai-bot-case-automation", "mock_mode": self.settings.mock_salesforce})

        @flask_app.route("/webhook/salesforce", methods=["POST"])
        def salesforce_webhook():
            payload = request.get_json(silent=True) or {}
            case = self._parse_webhook_payload(payload)
            if not case:
                return jsonify({"error": "Invalid payload"}), 400

            record = self.processor.process(case)
            if record:
                self._record_notification(record)
                return jsonify({"status": "notified", "engineer": record.engineer_id}), 200

            return jsonify({"status": "skipped", "reason": "non-actionable"}), 200

        return flask_app

    def _parse_webhook_payload(self, payload: dict) -> SupportCase | None:
        data = payload.get("case") or payload
        case_id = data.get("Id") or data.get("case_id")
        if not case_id:
            return None

        now = datetime.now(timezone.utc)
        return SupportCase(
            case_id=case_id,
            case_number=data.get("CaseNumber") or data.get("case_number") or case_id,
            subject=data.get("Subject") or data.get("subject") or "",
            description=data.get("Description") or data.get("description") or "",
            priority=data.get("Priority") or data.get("priority") or "Medium",
            status=data.get("Status") or data.get("status") or "New",
            account_name=(data.get("Account") or {}).get("Name") or data.get("account_name") or "Unknown",
            contact_name=(data.get("Contact") or {}).get("Name") or data.get("contact_name") or "Unknown",
            product=data.get("Product__c") or data.get("product") or "Unknown",
            region=data.get("Region__c") or data.get("region") or "AMER",
            is_key_customer=bool(data.get("Key_Customer__c") or data.get("is_key_customer")),
            created_at=now,
            salesforce_url=data.get("salesforce_url")
            or f"{self.settings.salesforce_instance_url}/lightning/r/Case/{case_id}/view",
            raw=data,
        )

    def _record_notification(self, record: NotificationRecord) -> None:
        self.notification_history.append(record)
        self.stats["notified"] += 1

    def poll_once(self) -> None:
        cases = self.case_source.fetch_new_cases()
        for case in cases:
            self.stats["processed"] += 1
            record = self.processor.process(case)
            if record:
                self._record_notification(record)
                logger.info(
                    "Auto-notification sent for %s → engineer %s",
                    case.case_number,
                    record.engineer_id,
                )
            else:
                self.stats["skipped"] += 1

    def _poll_loop(self) -> None:
        logger.info("Starting Salesforce poll loop (interval=%ss)", self.settings.poll_interval_seconds)
        while not self._stop_polling.is_set():
            try:
                self.poll_once()
            except Exception as exc:
                logger.exception("Poll cycle failed: %s", exc)
            self._stop_polling.wait(self.settings.poll_interval_seconds)

    def start_polling(self) -> None:
        if self._poll_thread and self._poll_thread.is_alive():
            return
        self._stop_polling.clear()
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def stop_polling(self) -> None:
        self._stop_polling.set()

    def run(self) -> None:
        self.start_polling()

        webhook_thread = threading.Thread(
            target=lambda: self.webhook_app.run(
                host="0.0.0.0",
                port=self.settings.webhook_port,
                debug=False,
                use_reloader=False,
            ),
            daemon=True,
        )
        webhook_thread.start()
        logger.info("Webhook server listening on port %s", self.settings.webhook_port)

        if not self.settings.slack_app_token:
            logger.warning("SLACK_APP_TOKEN not set — running webhook-only mode")
            while True:
                time.sleep(3600)
            return

        handler = SocketModeHandler(self.app, self.settings.slack_app_token)
        logger.info(
            f"{BOT_DISPLAY_NAME} is running — mock cases will auto-DM engineers (no slash commands needed)"
        )
        handler.start()
