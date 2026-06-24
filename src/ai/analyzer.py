from __future__ import annotations

import json
import logging
import re
from typing import Iterable

from src.config import is_valid_openai_api_key, load_json_config
from src.models import CaseAnalysis, RequestType, Severity, SupportCase

logger = logging.getLogger(__name__)

SEVERITY_PATTERNS = {
    Severity.SEV1: [r"\bsev\s*1\b", r"\bseverity\s*1\b", r"\boutage\b", r"\bproduction down\b"],
    Severity.SEV2: [r"\bsev\s*2\b", r"\bseverity\s*2\b", r"\bhigh priority\b"],
    Severity.SEV3: [r"\bsev\s*3\b", r"\bseverity\s*3\b"],
}

PRIORITY_TO_SEVERITY = {
    "critical": Severity.SEV1,
    "high": Severity.SEV2,
    "medium": Severity.SEV3,
    "low": Severity.UNKNOWN,
}


class CaseAnalyzer:
    """Analyzes support cases using OpenAI when available, otherwise rule-based logic."""

    def __init__(self, openai_api_key: str = "", openai_model: str = "gpt-4o-mini", notify_sev3: bool = False):
        self.openai_api_key = openai_api_key.strip() if openai_api_key else ""
        self.openai_model = openai_model
        self.routing_rules = load_json_config("routing_rules.json")
        self.notify_sev3 = notify_sev3 or self.routing_rules.get("notify_sev3", False)
        self.use_openai = is_valid_openai_api_key(self.openai_api_key)

        if self.openai_api_key and not self.use_openai:
            logger.info("OpenAI API key is missing or a placeholder — using rule-based analysis")
        elif self.use_openai:
            logger.info("OpenAI analysis enabled (model=%s)", self.openai_model)

    def analyze(self, case: SupportCase) -> CaseAnalysis:
        if self.use_openai:
            try:
                return self._analyze_with_openai(case)
            except Exception as exc:
                logger.warning("OpenAI analysis failed, disabling OpenAI and using rules: %s", exc)
                self.use_openai = False

        return self._analyze_with_rules(case)

    def _analyze_with_rules(self, case: SupportCase) -> CaseAnalysis:
        text = f"{case.subject}\n{case.description}".lower()
        severity = self._detect_severity(case, text)
        request_types = self._detect_request_types(case, text)
        required_skills = self._derive_skills(severity, request_types, case)
        is_actionable = self._is_actionable(severity, request_types, case)

        summary = self._build_summary(case, severity, request_types)
        reasoning = (
            f"Rule-based analysis: severity={severity.value}, "
            f"types={[t.value for t in request_types]}, "
            f"key_customer={case.is_key_customer}"
        )

        return CaseAnalysis(
            severity=severity,
            request_types=request_types,
            is_actionable=is_actionable,
            summary=summary,
            reasoning=reasoning,
            required_skills=required_skills,
            confidence=0.75,
            used_ai=False,
        )

    def _analyze_with_openai(self, case: SupportCase) -> CaseAnalysis:
        from openai import OpenAI

        client = OpenAI(api_key=self.openai_api_key)
        prompt = {
            "case_number": case.case_number,
            "subject": case.subject,
            "description": case.description,
            "priority": case.priority,
            "product": case.product,
            "region": case.region,
            "is_key_customer": case.is_key_customer,
            "instructions": (
                "Classify this support case. Return JSON with keys: "
                "severity (Sev1|Sev2|Sev3|Unknown), "
                "request_types (array from: Remote Session, Troubleshooting Assistance, "
                "Product Expertise, Customer Escalation, Key Customer Request, Service Request, General Support), "
                "is_actionable (bool), summary (1 sentence), reasoning (brief), "
                "required_skills (array of lowercase skill tags), confidence (0-1)."
            ),
        }

        response = client.chat.completions.create(
            model=self.openai_model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are AI-BOT-Case-Automation, a support triage assistant. "
                        "Flag cases needing immediate engineer attention: Sev1/Sev2, "
                        "remote sessions, escalations, key customers, and service requests."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt)},
            ],
            temperature=0.1,
        )

        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)

        severity = Severity(payload.get("severity", "Unknown"))
        request_types = [
            RequestType(value) for value in payload.get("request_types", []) if value in RequestType._value2member_map_
        ]
        if not request_types:
            request_types = [RequestType.GENERAL]

        analysis = CaseAnalysis(
            severity=severity,
            request_types=request_types,
            is_actionable=bool(payload.get("is_actionable", False)),
            summary=str(payload.get("summary", case.subject)),
            reasoning=str(payload.get("reasoning", "AI classification")),
            required_skills=[s.lower() for s in payload.get("required_skills", [])],
            confidence=float(payload.get("confidence", 0.85)),
            used_ai=True,
        )

        if analysis.severity == Severity.SEV3 and not self.notify_sev3:
            analysis.is_actionable = analysis.is_actionable and any(
                t != RequestType.GENERAL for t in analysis.request_types
            )

        return analysis

    def _detect_severity(self, case: SupportCase, text: str) -> Severity:
        for severity, patterns in SEVERITY_PATTERNS.items():
            if any(re.search(pattern, text) for pattern in patterns):
                return severity

        priority_severity = PRIORITY_TO_SEVERITY.get(case.priority.lower())
        if priority_severity:
            return priority_severity

        return Severity.UNKNOWN

    def _detect_request_types(self, case: SupportCase, text: str) -> list[RequestType]:
        types: list[RequestType] = []
        rules = self.routing_rules

        if any(kw in text for kw in rules.get("remote_session_keywords", [])):
            types.append(RequestType.REMOTE_SESSION)

        if any(kw in text for kw in rules.get("escalation_keywords", [])):
            types.append(RequestType.CUSTOMER_ESCALATION)

        if case.is_key_customer:
            types.append(RequestType.KEY_CUSTOMER)

        if any(word in text for word in ["troubleshoot", "debug", "root cause", "investigate"]):
            types.append(RequestType.TROUBLESHOOTING)

        if any(word in text for word in ["architecture", "best practice", "expert", "consultation"]):
            types.append(RequestType.PRODUCT_EXPERTISE)

        if any(word in text for word in ["service request", "engineer involvement", "hands-on"]):
            types.append(RequestType.SERVICE_REQUEST)

        return types or [RequestType.GENERAL]

    def _derive_skills(
        self,
        severity: Severity,
        request_types: Iterable[RequestType],
        case: SupportCase,
    ) -> list[str]:
        skills: set[str] = set()

        if severity == Severity.SEV1:
            skills.update(["sev1", "kubernetes", "networking"])
        elif severity == Severity.SEV2:
            skills.add("sev2")
        elif severity == Severity.SEV3:
            skills.add("sev3")

        mapping = {
            RequestType.REMOTE_SESSION: {"remote-session", "troubleshooting"},
            RequestType.TROUBLESHOOTING: {"troubleshooting"},
            RequestType.PRODUCT_EXPERTISE: {"product-expertise"},
            RequestType.CUSTOMER_ESCALATION: {"escalation", "sev1"},
            RequestType.KEY_CUSTOMER: {"key-customer"},
            RequestType.SERVICE_REQUEST: {"service-request"},
        }

        for request_type in request_types:
            skills.update(mapping.get(request_type, set()))

        product = case.product.lower()
        if "database" in product:
            skills.add("database")
        if "platform" in product:
            skills.add("networking")

        return sorted(skills)

    def _is_actionable(
        self,
        severity: Severity,
        request_types: list[RequestType],
        case: SupportCase,
    ) -> bool:
        if severity in {Severity.SEV1, Severity.SEV2}:
            return True

        if severity == Severity.SEV3 and self.notify_sev3:
            return True

        actionable_types = {
            RequestType.REMOTE_SESSION,
            RequestType.TROUBLESHOOTING,
            RequestType.PRODUCT_EXPERTISE,
            RequestType.CUSTOMER_ESCALATION,
            RequestType.KEY_CUSTOMER,
            RequestType.SERVICE_REQUEST,
        }

        if any(t in actionable_types for t in request_types):
            return True

        if case.is_key_customer and RequestType.GENERAL not in request_types:
            return True

        return False

    def _build_summary(
        self,
        case: SupportCase,
        severity: Severity,
        request_types: list[RequestType],
    ) -> str:
        type_label = request_types[0].value if request_types else "Support request"
        return (
            f"{severity.value} {type_label} from {case.account_name} "
            f"({case.product}, {case.region}): {case.subject}"
        )
