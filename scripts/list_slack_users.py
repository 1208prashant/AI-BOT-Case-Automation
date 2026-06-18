#!/usr/bin/env python3
"""List Slack workspace members and their user IDs — use these in config/engineers.json."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from slack_sdk import WebClient

load_dotenv(ROOT / ".env")

from src.config import load_settings


def main() -> None:
    settings = load_settings()
    if not settings.slack_bot_token:
        print("Error: SLACK_BOT_TOKEN not set in .env")
        sys.exit(1)

    client = WebClient(token=settings.slack_bot_token)
    cursor = None
    users: list[dict] = []

    while True:
        response = client.users_list(cursor=cursor, limit=200)
        users.extend(response.get("members", []))
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    print("\nSlack users in your workspace:\n")
    print(f"{'Name':<25} {'User ID':<15} {'Email'}")
    print("-" * 70)

    for member in sorted(users, key=lambda m: m.get("real_name") or m.get("name", "")):
        if member.get("deleted") or member.get("is_bot"):
            continue
        profile = member.get("profile", {})
        name = member.get("real_name") or member.get("name", "?")
        user_id = member.get("id", "?")
        email = profile.get("email") or "(hidden on free plan)"
        print(f"{name:<25} {user_id:<15} {email}")

    print("\nCopy your User ID (starts with U) into config/engineers.json")
    print('Example: "slack_user_id": "U07ABC123XY"\n')


if __name__ == "__main__":
    main()
