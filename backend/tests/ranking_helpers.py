"""Hand-calculated 100-mile summary fixtures, independent of sampling/risk logic."""

from dataclasses import replace
from fractions import Fraction
from types import MappingProxyType

from domain.aggregation import RouteSummary, TravelStatus
from domain.recommendation_types import RankingInput
from domain.risk_types import RiskLevel
from domain.route_types import Coordinate

from tests.route_helpers import straight_route


def option(
    path: int,
    *,
    severe: str | int = 0,
    high: str | int = 0,
    moderate: str | int = 0,
    no_travel: str | int = 0,
    duration: str | int = 6000,
    unknown: str | int = 0,
    known_block: bool = False,
) -> RankingInput:
    """Mean=(Low+2Moderate+3High+4Severe+5NoTravel)/100 when complete.

    Changing longitude supplies a distinct traveled path, rather than an ID
    based on input position. The same path always derives the same canonical ID.
    """
    miles = dict.fromkeys(RiskLevel, Fraction(0))
    miles[RiskLevel.MODERATE] = Fraction(moderate)
    miles[RiskLevel.HIGH] = Fraction(high)
    miles[RiskLevel.SEVERE] = Fraction(severe)
    miles[RiskLevel.NO_TRAVEL] = Fraction(no_travel)
    missing = Fraction(unknown)
    miles[RiskLevel.LOW] = 100 - sum(miles.values()) - missing
    assert miles[RiskLevel.LOW] >= 0
    weighted = sum((level.ordinal * distance for level, distance in miles.items()), Fraction(0))
    complete = missing == 0
    blocked = known_block or miles[RiskLevel.NO_TRAVEL] > 0
    status = (
        TravelStatus.BLOCKED
        if blocked
        else (TravelStatus.ASSESSED if complete else TravelStatus.INCOMPLETE)
    )
    levels = [level for level, distance in miles.items() if distance]
    if blocked:
        levels.append(RiskLevel.NO_TRAVEL)
    peak = max(levels, default=None)
    summary = RouteSummary(
        total_miles=Fraction(100),
        total_duration_s=Fraction(duration),
        miles_by_level=MappingProxyType(miles),
        unknown_miles=missing,
        average_risk=weighted / 100 if complete else None,
        known_only_average_risk_diagnostic=weighted / (100 - missing) if missing < 100 else None,
        maximum_known_level=peak,
        known_risk_floor=peak,
        no_travel_checkpoint_count=int(miles[RiskLevel.NO_TRAVEL] > 0),
        no_travel_miles=miles[RiskLevel.NO_TRAVEL],
        known_blocked_checkpoint_count=int(blocked),
        known_blocked_miles_diagnostic=(missing if known_block else miles[RiskLevel.NO_TRAVEL]),
        known_blocked=blocked,
        travel_status=status,
        coverage_fraction=(100 - missing) / 100,
    )
    route = straight_route(100, times_s=(0, duration))
    route = replace(
        route,
        geometry=tuple(Coordinate(p.longitude + path * 2, p.latitude) for p in route.geometry),
    )
    return RankingInput(route, summary)
