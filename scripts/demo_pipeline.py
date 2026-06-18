#!/usr/bin/env python3
"""Run AI-BOT-Case-Automation pipeline locally without Slack."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ai.analyzer import CaseAnalyzer
from src.models import SupportCase
from src.routing.router import EngineerRouter

SAMPLE_CASES = [
    {
        "case_number": "CS-9001",
        "subject": "Sev1 — Production outage on Platform A",
        "description": "Complete service outage. Executive escalation. All AMER users affected.",
        "priority": "Critical",
        "product": "Platform A",
        "region": "AMER",
        "is_key_customer": True,
    },
    {
        "case_number": "CS-9002",
        "subject": "Remote session needed for database migration",
        "description": "Customer requests Zoom screen share for live troubleshooting.",
        "priority": "High",
        "product": "Database Suite",
        "region": "EMEA",
        "is_key_customer": False,
    },
    {
        "case_number": "CS-9003",
        "subject": "How to reset password?",
        "description": "User forgot password on staging environment.",
        "priority": "Low",
        "product": "Platform A",
        "region": "AMER",
        "is_key_customer": False,
    },
]


def main() -> None:
    analyzer = CaseAnalyzer()
    router = EngineerRouter()

    print("=" * 60)
    print(f"{BOT_DISPLAY_NAME} — Local Pipeline Demo (no Slack required)")
    print("=" * 60)

    for sample in SAMPLE_CASES:
        case = SupportCase(
            case_id=sample["case_number"],
            case_number=sample["case_number"],
            subject=sample["subject"],
            description=sample["description"],
            priority=sample["priority"],
            status="New",
            account_name="Demo Account",
            contact_name="Demo Contact",
            product=sample["product"],
            region=sample["region"],
            is_key_customer=sample["is_key_customer"],
            created_at=datetime.now(timezone.utc),
            salesforce_url="https://example.my.salesforce.com",
        )

        analysis = analyzer.analyze(case)
        routing = router.route(case, analysis) if analysis.is_actionable else None

        result = {
            "case": case.case_number,
            "actionable": analysis.is_actionable,
            "severity": analysis.severity.value,
            "request_types": [t.value for t in analysis.request_types],
            "summary": analysis.summary,
            "assigned_to": routing.engineer.name if routing else None,
            "routing_score": routing.score if routing else None,
            "rationale": routing.rationale if routing else None,
        }
        print(json.dumps(result, indent=2))
        print("-" * 60)


if __name__ == "__main__":
    main()
