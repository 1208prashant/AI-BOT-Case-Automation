from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"

BOT_DISPLAY_NAME = "AI-BOT-Case-Automation"
BOT_SLASH_PREFIX = "aibot"

load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    slack_bot_token: str
    slack_app_token: str
    slack_signing_secret: str
    salesforce_instance_url: str
    salesforce_client_id: str
    salesforce_client_secret: str
    salesforce_username: str
    salesforce_password: str
    salesforce_security_token: str
    openai_api_key: str
    openai_model: str
    mock_salesforce: bool
    poll_interval_seconds: int
    mock_case_interval_seconds: int
    notify_sev3: bool
    webhook_port: int
    log_level: str


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_valid_openai_api_key(key: str | None) -> bool:
    """Return True only for a non-empty, non-placeholder OpenAI API key."""
    if not key or not key.strip():
        return False

    normalized = key.strip()
    lower = normalized.lower()

    placeholder_markers = (
        "your-openai",
        "your_openai",
        "sk-your",
        "sk-xxx",
        "changeme",
        "placeholder",
        "example.com",
        "<",
        ">",
    )
    if any(marker in lower for marker in placeholder_markers):
        return False

    if not normalized.startswith("sk-"):
        return False

    # Real OpenAI keys are significantly longer than template values.
    if len(normalized) < 40:
        return False

    return True


def load_settings() -> Settings:
    return Settings(
        slack_bot_token=os.getenv("SLACK_BOT_TOKEN", ""),
        slack_app_token=os.getenv("SLACK_APP_TOKEN", ""),
        slack_signing_secret=os.getenv("SLACK_SIGNING_SECRET", ""),
        salesforce_instance_url=os.getenv("SALESFORCE_INSTANCE_URL", ""),
        salesforce_client_id=os.getenv("SALESFORCE_CLIENT_ID", ""),
        salesforce_client_secret=os.getenv("SALESFORCE_CLIENT_SECRET", ""),
        salesforce_username=os.getenv("SALESFORCE_USERNAME", ""),
        salesforce_password=os.getenv("SALESFORCE_PASSWORD", ""),
        salesforce_security_token=os.getenv("SALESFORCE_SECURITY_TOKEN", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        mock_salesforce=_bool(os.getenv("MOCK_SALESFORCE"), default=True),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "15")),
        mock_case_interval_seconds=int(os.getenv("MOCK_CASE_INTERVAL_SECONDS", "45")),
        notify_sev3=_bool(os.getenv("NOTIFY_SEV3"), default=False),
        webhook_port=int(os.getenv("WEBHOOK_PORT", "3000")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


def load_json_config(filename: str) -> dict:
    path = CONFIG_DIR / filename
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)
