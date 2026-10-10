"""MET-01..04: hand-derived disjoint mileage, exact averages and known blocks."""

from collections.abc import MutableMapping
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from decimal import Decimal
from fractions import Fraction
from typing import cast

import pytest
from domain.aggregation import TravelStatus, aggregate_route
from domain.checkpoints import generate_checkpoints
from domain.risk import classify_checkpoint
from domain.risk_types import CheckpointRisk, RiskLevel
from domain.route_types import Ownership, RouteError

from tests.route_helpers import straight_route

F = Fraction
DEPARTURE = datetime(2026, 10, 10, 12, tzinfo=UTC)


def classified(level: RiskLevel | None, *, known_block: bool = False) -> CheckpointRisk:
    """Use the real risk engine for every test level; never manufacture classification."""
    if level is None:
        return classify_checkpoint(
            wind_mph=55 if known_block else None,
            rain_in_per_hour=None,
            snow_in_per_hour=None,
            load_weight_lb=0,
        )
    rain = {
        RiskLevel.LOW: "0",
        RiskLevel.MODERATE: ".1",
        RiskLevel.HIGH: ".25",
        RiskLevel.SEVERE: ".5",
        RiskLevel.NO_TRAVEL: "1.0001",
    }[level]
    return classify_checkpoint(
        wind_mph=0, rain_in_per_hour=Decimal(rain), snow_in_per_hour=0, load_weight_lb=0
    )


def test_hand_calculated_23_mile_summary() -> None:
    """Ownership[5,10,6.5,1.5] x levels[1,4,3,1] gives weighted66, mean66/23."""
    route = straight_route(23)
    checkpoints = generate_checkpoints(route, DEPARTURE, 10)
    risks = tuple(
        classified(level)
        for level in (RiskLevel.LOW, RiskLevel.SEVERE, RiskLevel.HIGH, RiskLevel.LOW)
    )
    summary = aggregate_route(route, checkpoints, risks)
    assert summary.miles_by_level == {
        RiskLevel.LOW: F("6.5"),
        RiskLevel.MODERATE: 0,
        RiskLevel.HIGH: F("6.5"),
        RiskLevel.SEVERE: 10,
        RiskLevel.NO_TRAVEL: 0,
    }
    assert summary.average_risk == F(66, 23)
    assert summary.known_only_average_risk_diagnostic == F(66, 23)
    assert summary.coverage_fraction == 1 and summary.unknown_miles == 0
    assert summary.maximum_known_level is summary.known_risk_floor is RiskLevel.SEVERE
    assert summary.travel_status is TravelStatus.ASSESSED and not summary.known_blocked
    assert summary.total_duration_s == route.duration_s


def test_unknown_mileage_never_enters_complete_average() -> None:
    """Removing mile20's owned6.5 leaves16.5 known, weighted46.5; full mean stays null."""
    route = straight_route(23)
    checkpoints = generate_checkpoints(route, DEPARTURE, 10)
    risks = tuple(
        classified(level) for level in (RiskLevel.LOW, RiskLevel.SEVERE, None, RiskLevel.LOW)
    )
    summary = aggregate_route(route, checkpoints, risks)
    assert summary.unknown_miles == F("6.5")
    assert summary.coverage_fraction == F("16.5") / 23
    assert summary.average_risk is None
    assert summary.known_only_average_risk_diagnostic == F("46.5") / F("16.5")
    assert summary.travel_status is TravelStatus.INCOMPLETE
    assert sum(summary.miles_by_level.values()) + summary.unknown_miles == 23


def test_unknown_with_proven_no_travel_is_blocked_without_double_counting() -> None:
    route = straight_route(23)
    checkpoints = generate_checkpoints(route, DEPARTURE, 10)
    risks = (
        classified(RiskLevel.LOW),
        classified(RiskLevel.LOW),
        classified(None, known_block=True),
        classified(RiskLevel.LOW),
    )
    summary = aggregate_route(route, checkpoints, risks)
    assert summary.travel_status is TravelStatus.BLOCKED and summary.known_blocked
    assert summary.known_risk_floor is summary.maximum_known_level is RiskLevel.NO_TRAVEL
    assert summary.no_travel_miles == 0 and summary.no_travel_checkpoint_count == 0
    assert summary.known_blocked_checkpoint_count == 1
    assert summary.known_blocked_miles_diagnostic == summary.unknown_miles == F("6.5")
    assert summary.average_risk is None and summary.known_only_average_risk_diagnostic == 1
    assert sum(summary.miles_by_level.values()) + summary.unknown_miles == 23


@pytest.mark.parametrize("interval", [10, 25, 50])
def test_all_five_categories_and_unknown_are_exclusive(interval: int) -> None:
    route = straight_route(105)
    checkpoints = generate_checkpoints(route, DEPARTURE, interval)
    levels = (*tuple(RiskLevel), None)
    risks = tuple(classified(levels[i % len(levels)]) for i in range(len(checkpoints)))
    summary = aggregate_route(route, checkpoints, risks)
    assert sum(summary.miles_by_level.values()) + summary.unknown_miles == route.distance_miles
    for level in RiskLevel:
        expected = sum(
            (
                c.owned_miles
                for c, risk in zip(checkpoints, risks, strict=True)
                if risk.final_level is level
            ),
            F(0),
        )
        assert summary.miles_by_level[level] == expected
    assert summary.no_travel_miles == summary.miles_by_level[RiskLevel.NO_TRAVEL]
    assert summary.no_travel_checkpoint_count == sum(
        r.final_level is RiskLevel.NO_TRAVEL for r in risks
    )


@pytest.mark.parametrize("level", list(RiskLevel))
@pytest.mark.parametrize("interval", [10, 25, 50])
def test_uniform_complete_routes(level: RiskLevel, interval: int) -> None:
    route = straight_route(105)
    checkpoints = generate_checkpoints(route, DEPARTURE, interval)
    summary = aggregate_route(route, checkpoints, tuple(classified(level) for _ in checkpoints))
    assert summary.miles_by_level[level] == 105 and sum(summary.miles_by_level.values()) == 105
    assert summary.average_risk == level.ordinal
    assert summary.coverage_fraction == 1 and summary.unknown_miles == 0
    assert summary.travel_status is (
        TravelStatus.BLOCKED if level is RiskLevel.NO_TRAVEL else TravelStatus.ASSESSED
    )


@pytest.mark.parametrize("known_block", [False, True])
def test_all_unknown_routes_have_no_average(known_block: bool) -> None:
    route = straight_route(105)
    checkpoints = generate_checkpoints(route, DEPARTURE, 25)
    summary = aggregate_route(
        route, checkpoints, tuple(classified(None, known_block=known_block) for _ in checkpoints)
    )
    assert summary.average_risk is summary.known_only_average_risk_diagnostic is None
    assert summary.unknown_miles == 105 and summary.coverage_fraction == 0
    assert sum(summary.miles_by_level.values()) == 0
    assert summary.known_risk_floor is (RiskLevel.NO_TRAVEL if known_block else None)
    assert summary.travel_status is (
        TravelStatus.BLOCKED if known_block else TravelStatus.INCOMPLETE
    )


def test_unknown_with_severe_load_floor_retains_peak() -> None:
    route = straight_route(5)
    checkpoints = generate_checkpoints(route, DEPARTURE, 50)
    partial = classify_checkpoint(
        wind_mph=35, rain_in_per_hour=None, snow_in_per_hour=0, load_weight_lb=Decimal("40000.5")
    )
    summary = aggregate_route(route, checkpoints, (partial, partial))
    assert summary.known_risk_floor is summary.maximum_known_level is RiskLevel.SEVERE
    assert summary.average_risk is summary.known_only_average_risk_diagnostic is None
    assert summary.travel_status is TravelStatus.INCOMPLETE


def test_aggregation_rejects_misalignment_and_invented_ownership() -> None:
    route = straight_route(23)
    checkpoints = generate_checkpoints(route, DEPARTURE, 10)
    with pytest.raises(RouteError) as error:
        aggregate_route(route, checkpoints, (classified(RiskLevel.LOW),))
    assert error.value.code == "RISK_COUNT_MISMATCH"
    altered = (replace(checkpoints[0], ownership=Ownership(F(0), F(100))), *checkpoints[1:])
    with pytest.raises(RouteError) as error:
        aggregate_route(route, altered, tuple(classified(RiskLevel.LOW) for _ in checkpoints))
    assert error.value.code == "INVALID_OWNERSHIP"
    with pytest.raises(RouteError):
        aggregate_route(
            route,
            tuple(reversed(checkpoints)),
            tuple(classified(RiskLevel.LOW) for _ in checkpoints),
        )


def test_summary_is_immutable_and_repeatable() -> None:
    route = straight_route(5)
    checkpoints = generate_checkpoints(route, DEPARTURE, 50)
    risks = (classified(RiskLevel.LOW), classified(RiskLevel.SEVERE))
    result = aggregate_route(route, checkpoints, risks)
    assert result == aggregate_route(route, checkpoints, risks)
    with pytest.raises(FrozenInstanceError):
        field = "average_risk"
        setattr(result, field, F(0))
    with pytest.raises(TypeError):
        cast(MutableMapping[RiskLevel, Fraction], result.miles_by_level)[RiskLevel.LOW] = F(100)
