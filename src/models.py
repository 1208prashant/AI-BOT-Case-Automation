from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    SEV1 = "Sev1"
    SEV2 = "Sev2"
    SEV3 = "Sev3"
    UNKNOWN = "Unknown"


class RequestType(str, Enum):
    REMOTE_SESSION = "Remote Session"
    TROUBLESHOOTING = "Troubleshooting Assistance"
    PRODUCT_EXPERTISE = "Product Expertise"
    CUSTOMER_ESCALATION = "Customer Escalation"
    KEY_CUSTOMER = "Key Customer Request"
    SERVICE_REQUEST = "Service Request"
    GENERAL = "General Support"


@dataclass
class SupportCase:
    case_id: str
    case_number: str
    subject: str
    description: str
    priority: str
    status: str
    account_name: str
    contact_name: str
    product: str
    region: str
    is_key_customer: bool
    created_at: datetime
    salesforce_url: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class CaseAnalysis:
    severity: Severity
    request_types: list[RequestType]
    is_actionable: bool
    summary: str
    reasoning: str
    required_skills: list[str]
    confidence: float
    used_ai: bool = False


@dataclass
class Engineer:
    id: str
    name: str
    slack_user_id: str
    email: str
    skills: list[str]
    products: list[str]
    regions: list[str]
    on_call: bool
    max_active_cases: int
    active_case_count: int = 0


@dataclass
class RoutingDecision:
    engineer: Engineer
    score: float
    rationale: str


@dataclass
class NotificationRecord:
    case_id: str
    engineer_id: str
    slack_channel: str
    sent_at: datetime
    analysis: CaseAnalysis
