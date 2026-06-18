from __future__ import annotations

import logging
from dataclasses import dataclass

from src.config import load_json_config
from src.models import CaseAnalysis, Engineer, RoutingDecision, SupportCase

logger = logging.getLogger(__name__)


@dataclass
class EngineerLoadTracker:
    """Tracks how many cases each engineer has been assigned in this session."""

    counts: dict[str, int]

    def increment(self, engineer_id: str) -> None:
        self.counts[engineer_id] = self.counts.get(engineer_id, 0) + 1

    def get(self, engineer_id: str) -> int:
        return self.counts.get(engineer_id, 0)


class EngineerRouter:
    """Scores engineers by skill match, region, product, on-call status, and load."""

    ON_CALL_BONUS = 15
    REGION_MATCH_BONUS = 20
    PRODUCT_MATCH_BONUS = 15
    KEY_CUSTOMER_BONUS = 10
    LOAD_PENALTY = 8

    def __init__(self, load_tracker: EngineerLoadTracker | None = None):
        self.engineers = self._load_engineers()
        self.load_tracker = load_tracker or EngineerLoadTracker(counts={})

    def _load_engineers(self) -> list[Engineer]:
        config = load_json_config("engineers.json")
        return [
            Engineer(
                id=item["id"],
                name=item["name"],
                slack_user_id=item["slack_user_id"],
                email=item["email"],
                skills=[s.lower() for s in item["skills"]],
                products=item["products"],
                regions=item["regions"],
                on_call=item["on_call"],
                max_active_cases=item["max_active_cases"],
            )
            for item in config["engineers"]
        ]

    def route(self, case: SupportCase, analysis: CaseAnalysis) -> RoutingDecision | None:
        if not self.engineers:
            logger.error("No engineers configured")
            return None

        scored: list[tuple[Engineer, float, list[str]]] = []
        for engineer in self.engineers:
            score, reasons = self._score_engineer(engineer, case, analysis)
            scored.append((engineer, score, reasons))

        scored.sort(key=lambda item: item[1], reverse=True)
        best_engineer, best_score, reasons = scored[0]

        if best_score <= 0:
            logger.warning("No suitable engineer found for case %s", case.case_number)
            return None

        self.load_tracker.increment(best_engineer.id)
        rationale = "; ".join(reasons)
        logger.info(
            "Routed case %s to %s (score=%.1f): %s",
            case.case_number,
            best_engineer.name,
            best_score,
            rationale,
        )

        return RoutingDecision(engineer=best_engineer, score=best_score, rationale=rationale)

    def _score_engineer(
        self,
        engineer: Engineer,
        case: SupportCase,
        analysis: CaseAnalysis,
    ) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []

        skill_matches = set(analysis.required_skills) & set(engineer.skills)
        score += len(skill_matches) * 12
        if skill_matches:
            reasons.append(f"skills: {', '.join(sorted(skill_matches))}")

        if case.region in engineer.regions:
            score += self.REGION_MATCH_BONUS
            reasons.append(f"region match ({case.region})")

        if case.product in engineer.products:
            score += self.PRODUCT_MATCH_BONUS
            reasons.append(f"product match ({case.product})")

        if engineer.on_call:
            score += self.ON_CALL_BONUS
            reasons.append("on-call")

        if case.is_key_customer and "key-customer" in engineer.skills:
            score += self.KEY_CUSTOMER_BONUS
            reasons.append("key customer specialist")

        active = self.load_tracker.get(engineer.id)
        if active >= engineer.max_active_cases:
            score -= 50
            reasons.append("at capacity")
        else:
            score -= active * self.LOAD_PENALTY
            if active:
                reasons.append(f"current load: {active}")

        return score, reasons

    def list_engineers(self) -> list[Engineer]:
        return self.engineers

    def get_engineer_by_slack_id(self, slack_user_id: str) -> Engineer | None:
        for engineer in self.engineers:
            if engineer.slack_user_id == slack_user_id:
                return engineer
        return None
