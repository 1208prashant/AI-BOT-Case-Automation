#!/usr/bin/env python3
"""AI-BOT-Case-Automation entry point."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import load_settings
from src.slack.bot import CaseAutomationBot


def main() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not settings.slack_bot_token and not settings.mock_salesforce:
        logging.error("SLACK_BOT_TOKEN is required. Copy .env.example to .env and configure.")
        sys.exit(1)

    bot = CaseAutomationBot(settings)
    bot.run()


if __name__ == "__main__":
    main()
