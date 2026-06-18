from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Protocol

from src.models import SupportCase

logger = logging.getLogger(__name__)

MOCK_CASE_TEMPLATES = [
    {
        "subject": "PRODUCTION OUTAGE — Platform A cluster unreachable",
        "description": (
            "Customer reports complete service outage affecting all users in AMER region. "
            "Error 503 on all API endpoints. Executive escalation requested."
        ),
        "priority": "Critical",
        "product": "Platform A",
        "region": "AMER",
        "is_key_customer": True,
    },
    {
        "subject": "Request remote session for database migration issue",
        "description": (
            "Need live troubleshooting assistance via Zoom. Migration failing with "
            "constraint violations on production replica."
        ),
        "priority": "High",
        "product": "Database Suite",
        "region": "EMEA",
        "is_key_customer": False,
    },
    {
        "subject": "Sev2 — Intermittent latency on reporting dashboard",
        "description": (
            "Performance degradation on analytics dashboard. P95 latency increased 4x "
            "over last 2 hours. Customer needs root cause analysis."
        ),
        "priority": "High",
        "product": "Platform B",
        "region": "APAC",
        "is_key_customer": True,
    },
    {
        "subject": "Product expertise — Enterprise Suite integration question",
        "description": (
            "Key account requesting architecture guidance for SSO integration "
            "with custom IdP. Needs senior engineer consultation."
        ),
        "priority": "Medium",
        "product": "Enterprise Suite",
        "region": "EMEA",
        "is_key_customer": True,
    },
    {
        "subject": "General question about billing module",
        "description": "How do I export invoices for last quarter?",
        "priority": "Low",
        "product": "Platform A",
        "region": "AMER",
        "is_key_customer": False,
    },
]


class CaseSource(Protocol):
    def fetch_new_cases(self) -> list[SupportCase]: ...


class MockSalesforceClient:
    """Generates realistic mock cases for prototype testing."""

    def __init__(self, interval_seconds: int = 45) -> None:
        self.interval_seconds = interval_seconds
        self._seen_ids: set[str] = set()
        self._counter = 1000
        self._last_emit_at: datetime | None = None
        self._emit_on_next_poll = True

    def fetch_new_cases(self) -> list[SupportCase]:
        now = datetime.now(timezone.utc)

        if self._emit_on_next_poll:
            self._emit_on_next_poll = False
            self._last_emit_at = now
            case = self._create_case(now)
            logger.info("Mock Salesforce emitted startup case %s (auto-DM)", case.case_number)
            return [case]

        if self._last_emit_at is None:
            self._last_emit_at = now
            return []

        elapsed = (now - self._last_emit_at).total_seconds()
        if elapsed < self.interval_seconds:
            return []

        self._last_emit_at = now
        case = self._create_case(now)
        logger.info("Mock Salesforce emitted case %s (auto-DM in ~seconds)", case.case_number)
        return [case]

    def _create_case(self, now: datetime) -> SupportCase:
        template = random.choice(MOCK_CASE_TEMPLATES)
        self._counter += 1
        case_id = f"500{self._counter}"
        self._seen_ids.add(case_id)

        return SupportCase(
            case_id=case_id,
            case_number=f"CS-{self._counter}",
            subject=template["subject"],
            description=template["description"],
            priority=template["priority"],
            status="New",
            account_name="Acme Corp" if template["is_key_customer"] else "Beta Industries",
            contact_name="Jane Customer",
            product=template["product"],
            region=template["region"],
            is_key_customer=template["is_key_customer"],
            created_at=now,
            salesforce_url=f"https://example.my.salesforce.com/lightning/r/Case/{case_id}/view",
            raw=template,
        )


class SalesforceClient:
    """Minimal Salesforce REST client for Case polling."""

    TOKEN_PATH = "/services/oauth2/token"
    QUERY_PATH = "/services/data/v59.0/query"

    CASE_SOQL = """
        SELECT Id, CaseNumber, Subject, Description, Priority, Status,
               Account.Name, Contact.Name, Product__c, Region__c,
               Key_Customer__c, CreatedDate
        FROM Case
        WHERE Status IN ('New', 'Open')
          AND CreatedDate >= {since}
        ORDER BY CreatedDate DESC
        LIMIT 50
    """

    def __init__(
        self,
        instance_url: str,
        client_id: str,
        client_secret: str,
        username: str,
        password: str,
        security_token: str,
    ) -> None:
        self.instance_url = instance_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.security_token = security_token
        self._access_token: str | None = None
        self._seen_ids: set[str] = set()

    def _authenticate(self) -> None:
        import requests

        response = requests.post(
            f"{self.instance_url}{self.TOKEN_PATH}",
            data={
                "grant_type": "password",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "username": self.username,
                "password": f"{self.password}{self.security_token}",
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        self._access_token = payload["access_token"]

    def fetch_new_cases(self) -> list[SupportCase]:
        import requests

        if not self._access_token:
            self._authenticate()

        since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
        soql = self.CASE_SOQL.format(since=since).strip()
        headers = {"Authorization": f"Bearer {self._access_token}"}

        response = requests.get(
            f"{self.instance_url}{self.QUERY_PATH}",
            params={"q": soql},
            headers=headers,
            timeout=30,
        )
        if response.status_code == 401:
            self._authenticate()
            headers["Authorization"] = f"Bearer {self._access_token}"
            response = requests.get(
                f"{self.instance_url}{self.QUERY_PATH}",
                params={"q": soql},
                headers=headers,
                timeout=30,
            )
        response.raise_for_status()

        records = response.json().get("records", [])
        cases: list[SupportCase] = []
        for record in records:
            case_id = record["Id"]
            if case_id in self._seen_ids:
                continue
            self._seen_ids.add(case_id)
            account = record.get("Account") or {}
            contact = record.get("Contact") or {}
            created_raw = record.get("CreatedDate", "")
            created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))

            cases.append(
                SupportCase(
                    case_id=case_id,
                    case_number=record.get("CaseNumber", case_id),
                    subject=record.get("Subject", ""),
                    description=record.get("Description") or "",
                    priority=record.get("Priority", "Medium"),
                    status=record.get("Status", "New"),
                    account_name=account.get("Name", "Unknown"),
                    contact_name=contact.get("Name", "Unknown"),
                    product=record.get("Product__c") or "Unknown",
                    region=record.get("Region__c") or "AMER",
                    is_key_customer=bool(record.get("Key_Customer__c")),
                    created_at=created_at,
                    salesforce_url=f"{self.instance_url}/lightning/r/Case/{case_id}/view",
                    raw=record,
                )
            )
        return cases
