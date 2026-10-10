"""Exact mileage partition and risk diagnostics; no recommendation or classification."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from types import MappingProxyType

from domain.checkpoints import midpoint_ownership
from domain.risk_types import UNKNOWN, CheckpointRisk, RiskLevel
from domain.route_types import Checkpoint, Route, RouteError


class TravelStatus(StrEnum):
    BLOCKED = "BLOCKED"
    ASSESSED = "ASSESSED"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True, slots=True)
class RouteSummary:
    """Disjoint final categories; overlapping known-block evidence is diagnostic.

    Both peak fields expose the highest proven level, including UNKNOWN floors.
    The known-only mean uses complete final observations only, never a guessed
    UNKNOWN ordinal. Future ranking must use average_risk and complete eligibility.
    """

    total_miles: Fraction
    total_duration_s: Fraction
    miles_by_level: Mapping[RiskLevel, Fraction]
    unknown_miles: Fraction
    average_risk: Fraction | None
    known_only_average_risk_diagnostic: Fraction | None
    maximum_known_level: RiskLevel | None
    known_risk_floor: RiskLevel | None
    no_travel_checkpoint_count: int
    no_travel_miles: Fraction
    known_blocked_checkpoint_count: int
    known_blocked_miles_diagnostic: Fraction
    known_blocked: bool
    travel_status: TravelStatus
    coverage_fraction: Fraction


def aggregate_route(
    route: Route,
    checkpoints: Sequence[Checkpoint],
    risks: Sequence[CheckpointRisk],
) -> RouteSummary:
    """Combine existing risk-engine results without duplicating weather/load rules."""
    if len(checkpoints) != len(risks):
        raise RouteError(
            "RISK_COUNT_MISMATCH", "Each checkpoint must have one classification result."
        )
    ownership = midpoint_ownership(
        tuple(c.distance_m for c in checkpoints), route.distance_m, route.policy
    )
    if any(c.ownership != owned for c, owned in zip(checkpoints, ownership, strict=True)):
        raise RouteError(
            "INVALID_OWNERSHIP",
            "Checkpoint ownership does not match this route's midpoint partition.",
        )
    miles = dict.fromkeys(RiskLevel, Fraction(0))
    unknown = Fraction(0)
    weighted = Fraction(0)
    known_levels: list[RiskLevel] = []
    final_no_travel = 0
    blocked_count = 0
    blocked_miles = Fraction(0)
    for checkpoint, risk in zip(checkpoints, risks, strict=True):
        if not isinstance(risk, CheckpointRisk):
            raise RouteError(
                "INVALID_RISK_RESULT", "Aggregation requires risk-engine checkpoint results."
            )
        if risk.final_level is UNKNOWN:
            unknown += checkpoint.owned_miles
        elif isinstance(risk.final_level, RiskLevel):
            miles[risk.final_level] += checkpoint.owned_miles
            weighted += checkpoint.owned_miles * risk.final_level.ordinal
            known_levels.append(risk.final_level)
            final_no_travel += int(risk.final_level is RiskLevel.NO_TRAVEL)
        else:
            raise RouteError("INVALID_RISK_RESULT", "Final risk must be a known level or UNKNOWN.")
        if risk.known_risk_floor is not None:
            known_levels.append(risk.known_risk_floor)
        if (
            risk.known_blocked
            or risk.known_risk_floor is RiskLevel.NO_TRAVEL
            or risk.final_level is RiskLevel.NO_TRAVEL
        ):
            blocked_count += 1
            blocked_miles += checkpoint.owned_miles
    known_miles = route.distance_miles - unknown
    complete = unknown == 0
    peak = max(known_levels, default=None)
    status = (
        TravelStatus.BLOCKED
        if blocked_count
        else (TravelStatus.ASSESSED if complete else TravelStatus.INCOMPLETE)
    )
    return RouteSummary(
        route.distance_miles,
        route.duration_s,
        MappingProxyType(miles),
        unknown,
        weighted / route.distance_miles if complete else None,
        weighted / known_miles if known_miles else None,
        peak,
        peak,
        final_no_travel,
        miles[RiskLevel.NO_TRAVEL],
        blocked_count,
        blocked_miles,
        bool(blocked_count),
        status,
        known_miles / route.distance_miles,
    )
