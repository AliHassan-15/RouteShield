"""Immutable ranking facts; exact Fractions are serialized by the later API layer."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from domain.aggregation import RouteSummary, TravelStatus
from domain.route_types import Route


class RankingGroup(StrEnum):
    ASSESSED = "ASSESSED"
    BLOCKED_COMPLETE = "BLOCKED_COMPLETE"
    UNRANKED = "UNRANKED"


class RecommendationStatus(StrEnum):
    RECOMMENDED = "RECOMMENDED"
    BEST_FULLY_ASSESSED_AVAILABLE = "BEST_FULLY_ASSESSED_AVAILABLE"
    ALL_BLOCKED = "ALL_BLOCKED"
    NO_FULLY_ASSESSED_TRAVELABLE_ROUTE = "NO_FULLY_ASSESSED_TRAVELABLE_ROUTE"
    ALL_INCOMPLETE = "ALL_INCOMPLETE"


class DecisionCriterion(StrEnum):
    SEVERE_MILES = "SEVERE_MILES"
    HIGH_MILES = "HIGH_MILES"
    AVERAGE_RISK = "AVERAGE_RISK"
    DURATION = "DURATION"
    TIE_BROKEN_BY_ID = "TIE_BROKEN_BY_ID"
    NONE = "NONE"


class ComparisonCriterion(StrEnum):
    NO_TRAVEL_MILES = "NO_TRAVEL_MILES"
    SEVERE_MILES = "SEVERE_MILES"
    HIGH_MILES = "HIGH_MILES"
    AVERAGE_RISK = "AVERAGE_RISK"
    DURATION = "DURATION"
    TIE_BROKEN_BY_ID = "TIE_BROKEN_BY_ID"
    ELIGIBILITY = "ELIGIBILITY"


class ExplanationCode(StrEnum):
    RECOMMENDED = "RECOMMENDED"
    BEST_FULLY_ASSESSED_AVAILABLE = "BEST_FULLY_ASSESSED_AVAILABLE"
    ALL_BLOCKED = "ALL_BLOCKED"
    NO_FULLY_ASSESSED_TRAVELABLE_ROUTE = "NO_FULLY_ASSESSED_TRAVELABLE_ROUTE"
    ALL_INCOMPLETE = "ALL_INCOMPLETE"
    SEVERE_MILES = "SEVERE_MILES"
    HIGH_MILES = "HIGH_MILES"
    AVERAGE_RISK = "AVERAGE_RISK"
    DURATION = "DURATION"
    TIE_BROKEN_BY_ID = "TIE_BROKEN_BY_ID"
    NO_TRAVEL_MILES = "NO_TRAVEL_MILES"
    PARTIAL_ROUTES = "PARTIAL_ROUTES"
    ASSESSED_BEFORE_BLOCKED = "ASSESSED_BEFORE_BLOCKED"
    INCOMPLETE_UNRANKED = "INCOMPLETE_UNRANKED"
    LEAST_BLOCKED_DIAGNOSTIC = "LEAST_BLOCKED_DIAGNOSTIC"
    LOWER_PRIORITY_DURATION_CLOSE = "LOWER_PRIORITY_DURATION_CLOSE"


@dataclass(frozen=True, slots=True)
class RankingInput:
    route: Route
    summary: RouteSummary


@dataclass(frozen=True, slots=True)
class CriterionValues:
    no_travel_miles: Fraction
    severe_miles: Fraction
    high_miles: Fraction
    average_risk: Fraction | None
    duration_seconds: Fraction
    stable_route_id: str


@dataclass(frozen=True, slots=True)
class RankedRoute:
    route_id: str
    group: RankingGroup
    rank: int | None
    travel_status: TravelStatus
    known_blocked: bool
    criteria: CriterionValues
    unknown_miles: Fraction
    coverage_fraction: Fraction


@dataclass(frozen=True, slots=True)
class ComparisonFact:
    winner_route_id: str
    other_route_id: str
    criterion: ComparisonCriterion
    winner_value: Fraction | str
    other_value: Fraction | str
    code: ExplanationCode


type ExplanationValue = Fraction | int | str | None


@dataclass(frozen=True, slots=True)
class ExplanationFact:
    code: ExplanationCode
    route_id: str | None
    other_route_id: str | None
    values: Mapping[str, ExplanationValue]


@dataclass(frozen=True, slots=True)
class Recommendation:
    routes: tuple[RankedRoute, ...]
    route_count: int
    recommended_route_id: str | None
    least_blocked_route_id: str | None
    recommendation_status: RecommendationStatus
    message: str
    decisive_criterion: DecisionCriterion
    diagnostic_decisive_criterion: ComparisonCriterion | None
    comparison_facts: tuple[ComparisonFact, ...]
    explanation_facts: tuple[ExplanationFact, ...]
    explanation: str
