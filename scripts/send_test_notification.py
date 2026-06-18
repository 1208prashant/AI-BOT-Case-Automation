#!/usr/bin/env python3
"""Send a test notification to a Slack user ID."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from slack_sdk import WebClient

load_dotenv(ROOT / ".env")

from src.ai.analyzer import CaseAnalyzer
from src.config import BOT_DISPLAY_NAME, load_settings
from src.models import RoutingDecision, SupportCase
from src.routing.router import EngineerRouter
from src.slack.notifications import build_case_notification_blocks, build_case_notification_text


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Send a {BOT_DISPLAY_NAME} test DM")
    parser.add_argument("--user-id", required=True, help="Slack user ID (e.g. U01234567)")
    parser.add_argument("--severity", default="Sev1", help="Case severity label")
    args = parser.parse_args()

    settings = load_settings()
    if not settings.slack_bot_token:
        print("Error: SLACK_BOT_TOKEN not set in .env")
        sys.exit(1)

    case = SupportCase(
        case_id="TEST-001",
        case_number="CS-TEST-001",
        subject=f"{args.severity} — {BOT_DISPLAY_NAME} test notification",
        description=f"This is a test case from {BOT_DISPLAY_NAME} prototype setup.",
        priority="Critical",
        status="New",
        account_name="Test Account",
        contact_name="Test User",
        product="Platform A",
        region="AMER",
        is_key_customer=True,
        created_at=datetime.now(timezone.utc),
        salesforce_url="https://example.my.salesforce.com",
    )

    analyzer = CaseAnalyzer(openai_api_key=settings.openai_api_key)
    analysis = analyzer.analyze(case)
    router = EngineerRouter()
    routing = router.route(case, analysis)

    if not routing:
        print("No routing decision — check engineer config")
        sys.exit(1)

    # Override assignee to the test user
    routing = RoutingDecision(
        engineer=routing.engineer,
        score=routing.score,
        rationale=f"Test override → {args.user_id}",
    )
    routing.engineer.slack_user_id = args.user_id

    client = WebClient(token=settings.slack_bot_token)
    dm = client.conversations_open(users=args.user_id)
    blocks = build_case_notification_blocks(case, analysis, routing)

    client.chat_postMessage(
        channel=dm["channel"]["id"],
        text=build_case_notification_text(case, analysis, routing),
        blocks=blocks,
    )
    print(f"Test notification sent to {args.user_id}")


if __name__ == "__main__":
    main()
