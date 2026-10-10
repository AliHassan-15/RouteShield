"""RANK-01..07: exact priorities, eligibility and input-order independence."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from decimal import Decimal
from fractions import Fraction
from itertools import permutations
from typing import cast

import pytest
from domain.aggregation import TravelStatus, aggregate_route
from domain.checkpoints import generate_checkpoints
from domain.identity import stable_route_id
from domain.recommendation import recommend_routes
from domain.recommendation_types import (
    ComparisonCriterion,
    DecisionCriterion,
    RankingGroup,
    RankingInput,
    RecommendationStatus,
)
from domain.risk import classify_checkpoint
from domain.risk_types import RiskLevel
from domain.route_types import RouteError

from tests.ranking_helpers import option
from tests.route_helpers import straight_route

F = Fraction


@pytest.mark.parametrize(
    ("inputs", "criterion"),
    [
        # Extra .001 Severe defeats both fewer High miles and hours saved.
        (
            (
                option(0, high=20, moderate=50, duration=18000),
                option(1, severe=".001", duration=600),
                option(2, severe=".002", high=1, duration=300),
            ),
            DecisionCriterion.SEVERE_MILES,
        ),
        # Equal Severe; fewer High beats much lower mean and hours saved.
        (
            (
                option(0, high=1, moderate=80, duration=18000),
                option(1, high=2, duration=600),
                option(2, high=3, duration=300),
            ),
            DecisionCriterion.HIGH_MILES,
        ),
        # Equal Severe/High; means 1.01 < 1.02 < 1.03, despite hours saved.
        (
            (
                option(0, moderate=1, duration=18000),
                option(1, moderate=2, duration=600),
                option(2, moderate=3, duration=300),
            ),
            DecisionCriterion.AVERAGE_RISK,
        ),
        # Equal Severe/High/mean=1; 600 < 601 < 602 seconds.
        (
            (option(0, duration=600), option(1, duration=601), option(2, duration=602)),
            DecisionCriterion.DURATION,
        ),
    ],
    ids=[
        "severe-defeats-hours-and-high",
        "high-defeats-average",
        "average-defeats-hours",
        "duration",
    ],
)
def test_each_priority_with_three_adversarial_routes(
    inputs: tuple[RankingInput, ...], criterion: DecisionCriterion
) -> None:
    result = recommend_routes(tuple(reversed(inputs)))
    assert result.recommended_route_id == stable_route_id(inputs[0].route)
    assert result.decisive_criterion is criterion
    assert tuple(r.route_id for r in result.routes) == tuple(
        stable_route_id(i.route) for i in inputs
    )
    assert [r.rank for r in result.routes] == [1, 2, 3]
    assert len(result.comparison_facts) == 2
    assert all(f.criterion.value == criterion.value for f in result.comparison_facts)


@pytest.mark.parametrize("criterion", ["severe", "high", "average", "duration"])
def test_differences_below_display_precision_are_not_ties(criterion: str) -> None:
    a, b = {
        "severe": (option(0, severe=".000001"), option(1, severe=".000002")),
        "high": (option(0, high=".000001"), option(1, high=".000002")),
        "average": (option(0, moderate=".000001"), option(1, moderate=".000002")),
        "duration": (option(0, duration="600.000001"), option(1, duration="600.000002")),
    }[criterion]
    result = recommend_routes((b, a))
    assert result.recommended_route_id == stable_route_id(a.route)
    fact = result.comparison_facts[0]
    assert isinstance(fact.winner_value, F) and isinstance(fact.other_value, F)
    assert fact.winner_value < fact.other_value
    assert "Raw values differ; displayed values are rounded." in result.explanation
    assert "exactly tied" not in result.explanation


@pytest.mark.parametrize("order", list(permutations(range(3))))
def test_exact_ties_use_geometry_id(order: tuple[int, ...]) -> None:
    inputs = tuple(option(i) for i in range(3))
    expected = sorted(stable_route_id(i.route) for i in inputs)
    result = recommend_routes(tuple(inputs[i] for i in order))
    assert [r.route_id for r in result.routes] == expected
    assert result.recommended_route_id == expected[0]
    assert result.decisive_criterion is DecisionCriterion.TIE_BROKEN_BY_ID
    assert all(f.criterion is ComparisonCriterion.TIE_BROKEN_BY_ID for f in result.comparison_facts)


@pytest.mark.parametrize("order", list(permutations(range(4))))
def test_every_four_route_permutation_has_identical_result(order: tuple[int, ...]) -> None:
    inputs = (
        option(0, severe=5),
        option(1),
        option(2, no_travel=1),
        option(3, unknown=20, known_block=True),
    )
    original = tuple(inputs)
    expected = recommend_routes(inputs)
    assert recommend_routes(tuple(inputs[i] for i in order)) == expected
    assert inputs == original


@pytest.mark.parametrize("order", list(permutations(range(4))))
@pytest.mark.parametrize("all_blocked", [False, True])
def test_no_recommendation_outcomes_are_stable_in_all_permutations(
    order: tuple[int, ...], all_blocked: bool
) -> None:
    inputs = (
        (
            option(0, no_travel=20),
            option(1, no_travel=10),
            option(2, unknown=20, known_block=True),
            option(3, unknown=100, known_block=True),
        )
        if all_blocked
        else tuple(option(i, unknown=20 + i * 10) for i in range(4))
    )
    assert recommend_routes(tuple(inputs[i] for i in order)) == recommend_routes(inputs)


def test_consumes_real_aggregates_without_risk_or_metric_reimplementation() -> None:
    routes = (straight_route(5), straight_route(6))
    departure = datetime(2026, 10, 10, 12, tzinfo=UTC)
    inputs = []
    for route, rain in zip(routes, (Decimal(".25"), Decimal(0)), strict=True):
        checkpoints = generate_checkpoints(route, departure, 10)
        risk = classify_checkpoint(
            wind_mph=0, rain_in_per_hour=rain, snow_in_per_hour=0, load_weight_lb=0
        )
        summary = aggregate_route(route, checkpoints, (risk,) * len(checkpoints))
        inputs.append(RankingInput(route, summary))
    result = recommend_routes(inputs)
    assert result.recommended_route_id == stable_route_id(routes[1])
    assert result.decisive_criterion is DecisionCriterion.HIGH_MILES
    assert (result.comparison_facts[0].winner_value, result.comparison_facts[0].other_value) == (
        F(0),
        F(5),
    )


def test_assessed_group_precedes_blocked_regardless_of_metrics() -> None:
    assessed = option(0, severe=90, duration=18000)  # Mean 3.7; still not blocked.
    blocked = option(1, no_travel=".001", duration=600)  # Mean 1.00004 is blocked.
    result = recommend_routes((blocked, assessed))
    assert result.routes[0].group is RankingGroup.ASSESSED
    assert result.routes[1].group is RankingGroup.BLOCKED_COMPLETE
    assert result.recommended_route_id == stable_route_id(assessed.route)
    assert result.least_blocked_route_id is None
    assert result.decisive_criterion is DecisionCriterion.NONE
    fact = result.comparison_facts[0]
    assert fact.criterion is ComparisonCriterion.ELIGIBILITY
    assert (fact.winner_value, fact.other_value) == ("ASSESSED", "BLOCKED_COMPLETE")


@pytest.mark.parametrize(
    ("inputs", "criterion"),
    [
        (
            (
                option(0, no_travel=10, severe=80, duration=18000),
                option(1, no_travel=15),
                option(2, no_travel=20),
            ),
            ComparisonCriterion.NO_TRAVEL_MILES,
        ),
        (
            (
                option(0, no_travel=10, high=80),
                option(1, no_travel=10, severe=1),
                option(2, no_travel=10, severe=2),
            ),
            ComparisonCriterion.SEVERE_MILES,
        ),
        (
            (
                option(0, no_travel=10, moderate=80),
                option(1, no_travel=10, high=1),
                option(2, no_travel=10, high=2),
            ),
            ComparisonCriterion.HIGH_MILES,
        ),
        (
            (
                option(0, no_travel=10, duration=18000),
                option(1, no_travel=10, moderate=1),
                option(2, no_travel=10, moderate=2),
            ),
            ComparisonCriterion.AVERAGE_RISK,
        ),
        (
            (
                option(0, no_travel=10, duration=600),
                option(1, no_travel=10, duration=601),
                option(2, no_travel=10, duration=602),
            ),
            ComparisonCriterion.DURATION,
        ),
    ],
)
def test_complete_blocked_ordering_continues_through_every_priority(
    inputs: tuple[RankingInput, ...], criterion: ComparisonCriterion
) -> None:
    result = recommend_routes(tuple(reversed(inputs)))
    assert result.recommendation_status is RecommendationStatus.ALL_BLOCKED
    assert result.recommended_route_id is None
    assert result.least_blocked_route_id == stable_route_id(inputs[0].route)
    assert result.diagnostic_decisive_criterion is criterion
    assert result.decisive_criterion is DecisionCriterion.NONE
    assert [r.route_id for r in result.routes] == [stable_route_id(i.route) for i in inputs]


def test_blocked_exact_tie_uses_id() -> None:
    result = recommend_routes((option(0, no_travel=10), option(1, no_travel=10)))
    assert result.least_blocked_route_id == min(r.route_id for r in result.routes)
    assert result.diagnostic_decisive_criterion is ComparisonCriterion.TIE_BROKEN_BY_ID


@pytest.mark.parametrize("known_block", [False, True])
def test_incomplete_is_unranked_even_if_known_average_would_win(known_block: bool) -> None:
    assessed = option(0, severe=90)  # Complete mean 3.7.
    incomplete = option(1, unknown=20, known_block=known_block)  # Known-only mean 1.
    result = recommend_routes((incomplete, assessed))
    row = next(r for r in result.routes if r.group is RankingGroup.UNRANKED)
    assert incomplete.summary.known_only_average_risk_diagnostic == 1
    assert row.criteria.average_risk is None and row.rank is None
    assert row.travel_status is (TravelStatus.BLOCKED if known_block else TravelStatus.INCOMPLETE)
    assert row.known_blocked == known_block
    assert result.recommended_route_id == stable_route_id(assessed.route)
    assert result.comparison_facts[0].criterion is ComparisonCriterion.ELIGIBILITY


def test_every_route_exposes_raw_values_and_all_competitors_have_facts() -> None:
    inputs = (option(0), option(1, high=1), option(2, no_travel=1), option(3, unknown=100))
    result = recommend_routes(inputs)
    assert {f.other_route_id for f in result.comparison_facts} == {
        stable_route_id(i.route) for i in inputs[1:]
    }
    for item in inputs:
        row = next(r for r in result.routes if r.route_id == stable_route_id(item.route))
        assert row.criteria.no_travel_miles is item.summary.no_travel_miles
        assert row.criteria.severe_miles is item.summary.miles_by_level[RiskLevel.SEVERE]
        assert row.criteria.high_miles is item.summary.miles_by_level[RiskLevel.HIGH]
        assert row.criteria.average_risk is item.summary.average_risk
        assert row.criteria.duration_seconds is item.summary.total_duration_s
        assert row.unknown_miles is item.summary.unknown_miles
        assert row.coverage_fraction is item.summary.coverage_fraction


def test_zero_routes_and_colliding_geometry_fail_loudly() -> None:
    with pytest.raises(RouteError, match="At least one route") as error:
        recommend_routes(())
    assert error.value.code == "NO_ROUTE"
    a = option(0)
    with pytest.raises(RouteError) as duplicate:
        recommend_routes((a, a))
    assert duplicate.value.code == "DUPLICATE_ROUTE_ID"


@pytest.mark.parametrize(
    "invalid", ["null-complete", "average-incomplete", "float-key", "status", "coverage"]
)
def test_invalid_summary_contract_is_rejected(invalid: str) -> None:
    a = option(0)
    changes = {
        "null-complete": replace(a.summary, average_risk=None),
        "average-incomplete": replace(a.summary, unknown_miles=F(20), coverage_fraction=F(4, 5)),
        "float-key": replace(a.summary, total_duration_s=cast(F, 6000.0)),
        "status": replace(a.summary, travel_status=TravelStatus.BLOCKED),
        "coverage": replace(a.summary, coverage_fraction=F(2)),
    }
    with pytest.raises(RouteError) as error:
        recommend_routes((replace(a, summary=changes[invalid]),))
    assert error.value.code == "INVALID_ROUTE_SUMMARY"


def test_result_and_explanation_facts_are_immutable() -> None:
    result = recommend_routes((option(0), option(1, unknown=20)))
    with pytest.raises(FrozenInstanceError):
        result.routes[0].rank = 5  # type: ignore[misc]
    with pytest.raises(TypeError):
        result.explanation_facts[-1].values["unknown_miles"] = F(0)  # type: ignore[index]
