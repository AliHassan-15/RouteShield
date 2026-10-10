"""RANK-06..08, MET-03 and UI explanation facts; no browser/UI implementation."""

from fractions import Fraction

import pytest
from domain.explanations import display_number, render_explanation
from domain.identity import stable_route_id
from domain.recommendation import recommend_routes
from domain.recommendation_types import (
    ComparisonCriterion,
    DecisionCriterion,
    ExplanationCode,
    RankingGroup,
    RankingInput,
    RecommendationStatus,
)

from tests.ranking_helpers import option

F = Fraction


@pytest.mark.parametrize(
    ("inputs", "status", "message", "diagnostic"),
    [
        (
            (option(0),),
            RecommendationStatus.BEST_FULLY_ASSESSED_AVAILABLE,
            "Best fully assessed available route",
            False,
        ),
        (
            (option(0), option(1)),
            RecommendationStatus.RECOMMENDED,
            "Recommended fully assessed route",
            False,
        ),
        (
            (option(0), option(1), option(2)),
            RecommendationStatus.RECOMMENDED,
            "Recommended fully assessed route",
            False,
        ),
        (
            (option(0), option(1, no_travel=10), option(2, unknown=20)),
            RecommendationStatus.BEST_FULLY_ASSESSED_AVAILABLE,
            "Best fully assessed available route",
            False,
        ),
        (
            (option(0, no_travel=10), option(1, no_travel=20)),
            RecommendationStatus.ALL_BLOCKED,
            "No safe route at this departure time and load",
            True,
        ),
        (
            (option(0, no_travel=10), option(1, unknown=20, known_block=True)),
            RecommendationStatus.ALL_BLOCKED,
            "No safe route at this departure time and load",
            True,
        ),
        (
            (option(0, unknown=20, known_block=True),),
            RecommendationStatus.ALL_BLOCKED,
            "No safe route at this departure time and load",
            False,
        ),
        (
            (option(0, unknown=20, known_block=True), option(1, unknown=100, known_block=True)),
            RecommendationStatus.ALL_BLOCKED,
            "No safe route at this departure time and load",
            False,
        ),
        (
            (option(0, no_travel=10), option(1, unknown=20)),
            RecommendationStatus.NO_FULLY_ASSESSED_TRAVELABLE_ROUTE,
            "No fully assessed travelable route",
            True,
        ),
        (
            (option(0, unknown=20, known_block=True), option(1, unknown=100)),
            RecommendationStatus.NO_FULLY_ASSESSED_TRAVELABLE_ROUTE,
            "No fully assessed travelable route",
            False,
        ),
        (
            (option(0, unknown=20),),
            RecommendationStatus.ALL_INCOMPLETE,
            "All routes have incomplete weather data",
            False,
        ),
        (
            (option(0, unknown=20), option(1, unknown=100), option(2, unknown=100)),
            RecommendationStatus.ALL_INCOMPLETE,
            "All routes have incomplete weather data",
            False,
        ),
    ],
)
def test_every_status_and_message(
    inputs: tuple[RankingInput, ...], status: RecommendationStatus, message: str, diagnostic: bool
) -> None:
    result = recommend_routes(inputs)
    assert result.recommendation_status is status
    assert result.message == message
    assert result.explanation.startswith(message)
    assert result.explanation == render_explanation(result.explanation_facts)
    assert result.explanation_facts[0].code.value == status.value
    assert (result.least_blocked_route_id is not None) == diagnostic
    if status in (
        RecommendationStatus.RECOMMENDED,
        RecommendationStatus.BEST_FULLY_ASSESSED_AVAILABLE,
    ):
        assert result.recommended_route_id is not None
        assert (
            next(r.group for r in result.routes if r.route_id == result.recommended_route_id)
            is RankingGroup.ASSESSED
        )
    else:
        assert result.recommended_route_id is None
        assert "Recommended fully assessed route:" not in result.explanation
        assert "Best fully assessed available route:" not in result.explanation
    if status is RecommendationStatus.ALL_BLOCKED:
        assert "Based on the assessed data" in result.explanation
    if status is RecommendationStatus.NO_FULLY_ASSESSED_TRAVELABLE_ROUTE:
        assert "No safe route" not in result.explanation
    if diagnostic:
        assert "this route is blocked and is not recommended" in result.explanation


@pytest.mark.parametrize(
    ("first", "second", "code", "expected_values", "text"),
    [
        (
            option(0, severe=1),
            option(1, severe=2),
            ExplanationCode.SEVERE_MILES,
            (F(1), F(2)),
            "Severe miles: 1.00 vs 2.00",
        ),
        (
            option(0, high=1),
            option(1, high=2),
            ExplanationCode.HIGH_MILES,
            (F(1), F(2)),
            "High miles: 1.00 vs 2.00",
        ),
        (
            option(0, moderate=1),
            option(1, moderate=2),
            ExplanationCode.AVERAGE_RISK,
            (F("1.01"), F("1.02")),
            "average risk: 1.010 vs 1.020",
        ),
        (
            option(0, duration=600),
            option(1, duration=660),
            ExplanationCode.DURATION,
            (F(600), F(660)),
            "travel time in minutes: 10.00 vs 11.00",
        ),
        (
            option(0, no_travel=10),
            option(1, no_travel=20),
            ExplanationCode.NO_TRAVEL_MILES,
            (F(10), F(20)),
            "No Travel miles: 10.00 vs 20.00",
        ),
    ],
)
def test_numeric_explanation_templates_preserve_both_raw_values(
    first: RankingInput,
    second: RankingInput,
    code: ExplanationCode,
    expected_values: tuple[Fraction, Fraction],
    text: str,
) -> None:
    result = recommend_routes((second, first))
    fact = next(f for f in result.explanation_facts if f.code is code)
    assert (fact.values["winner_value"], fact.values["other_value"]) == expected_values
    assert text in result.explanation
    assert fact.route_id == stable_route_id(first.route)
    assert fact.other_route_id == stable_route_id(second.route)


@pytest.mark.parametrize("blocked", [False, True])
def test_identifier_tie_is_explicit_in_structured_and_rendered_explanation(blocked: bool) -> None:
    result = recommend_routes(
        (option(0, no_travel=int(blocked)), option(1, no_travel=int(blocked)))
    )
    facts = [f for f in result.explanation_facts if f.code is ExplanationCode.TIE_BROKEN_BY_ID]
    assert len(facts) == 1
    assert facts[0].values["winner_value"] == min(r.route_id for r in result.routes)
    assert "exactly tied; stable geometry identifier order breaks the tie" in result.explanation


@pytest.mark.parametrize("count", [1, 2, 3])
def test_one_two_three_options_have_truthful_availability_facts(count: int) -> None:
    result = recommend_routes(tuple(option(i) for i in range(count)))
    partial = [f for f in result.explanation_facts if f.code is ExplanationCode.PARTIAL_ROUTES]
    assert result.route_count == count
    if count < 3:
        assert len(partial) == 1 and partial[0].values["route_count"] == count
        assert f"Only {count} of 3 requested route options are available." in result.explanation
    else:
        assert partial == [] and "Only" not in result.explanation


@pytest.mark.parametrize("known_block", [False, True])
def test_one_eligible_route_discloses_both_blocked_and_incomplete_alternatives(
    known_block: bool,
) -> None:
    inputs = (option(0), option(1, no_travel=10), option(2, unknown=20, known_block=known_block))
    result = recommend_routes(inputs)
    codes = {f.code for f in result.explanation_facts}
    assert {
        ExplanationCode.BEST_FULLY_ASSESSED_AVAILABLE,
        ExplanationCode.ASSESSED_BEFORE_BLOCKED,
        ExplanationCode.INCOMPLETE_UNRANKED,
    } <= codes
    assert "only one route is eligible" in result.explanation
    assert "is blocked; fully assessed routes" in result.explanation
    assert "is unranked: 80.0% coverage, 20.00 unknown miles" in result.explanation
    fact = next(
        f for f in result.explanation_facts if f.code is ExplanationCode.INCOMPLETE_UNRANKED
    )
    assert fact.values == {
        "coverage_fraction": F(4, 5),
        "unknown_miles": F(20),
        "known_blocked": known_block,
    }
    assert ("Known blocking evidence is retained." in result.explanation) == known_block


def test_each_competitor_has_its_actual_first_differentiator() -> None:
    # Winner mean=1; every later route first differs at a different priority.
    inputs = (
        option(0, duration=600),
        option(1, severe=1),
        option(2, high=1),
        option(3, moderate=1),
        option(4, duration=660),
        option(5, no_travel=1),
        option(6, unknown=20),
    )
    result = recommend_routes(inputs)
    expected = (
        ComparisonCriterion.SEVERE_MILES,
        ComparisonCriterion.HIGH_MILES,
        ComparisonCriterion.AVERAGE_RISK,
        ComparisonCriterion.DURATION,
        ComparisonCriterion.ELIGIBILITY,
        ComparisonCriterion.ELIGIBILITY,
    )
    for item, criterion in zip(inputs[1:], expected, strict=True):
        fact = next(
            f for f in result.comparison_facts if f.other_route_id == stable_route_id(item.route)
        )
        assert fact.criterion is criterion
    assert result.decisive_criterion is DecisionCriterion.DURATION  # Closest ranked runner-up.
    assert len(result.comparison_facts) == 6


@pytest.mark.parametrize("difference", ["0", "239.999999", "240", "240.000001", "3600"])
@pytest.mark.parametrize("direction", [-1, 1])
def test_near_duration_note_has_exact_presentation_only_boundary(
    difference: str, direction: int
) -> None:
    seconds = F(difference)
    first = option(0, duration=6000)
    second = option(1, severe=1, duration=str(6000 + direction * seconds))
    # str(Fraction) can contain '/', which fixtures retain exactly via Fraction.
    result = recommend_routes((second, first))
    notes = [
        f
        for f in result.explanation_facts
        if f.code is ExplanationCode.LOWER_PRIORITY_DURATION_CLOSE
    ]
    assert result.decisive_criterion is DecisionCriterion.SEVERE_MILES
    assert bool(notes) == (0 < seconds <= 240)
    if notes:
        assert notes[0].values["duration_difference_seconds"] == seconds
        assert "within 4 minutes" in result.explanation
        assert "did not decide this comparison" in result.explanation


def test_no_near_duration_note_when_duration_decides() -> None:
    result = recommend_routes((option(0, duration=600), option(1, duration=601)))
    assert result.decisive_criterion is DecisionCriterion.DURATION
    assert all(
        f.code is not ExplanationCode.LOWER_PRIORITY_DURATION_CLOSE
        for f in result.explanation_facts
    )


@pytest.mark.parametrize(
    ("value", "places", "expected"),
    [
        (F("1.005"), 2, "1.00"),
        (F("1.015"), 2, "1.02"),
        (F(1, 3), 3, ".333"),
        (F("-.005"), 2, "0.00"),
        (F(5, 2), 0, "2"),
    ],
)
def test_exact_half_even_display_only(value: Fraction, places: int, expected: str) -> None:
    if expected.startswith("."):
        expected = "0" + expected
    assert display_number(value, places) == expected


def test_all_machine_codes_have_an_exercised_template() -> None:
    scenarios = (
        (option(0), option(1)),
        (option(0),),
        (option(0, no_travel=1), option(1, no_travel=2)),
        (option(0, no_travel=1), option(1, unknown=20)),
        (option(0, unknown=100),),
        (option(0, severe=1), option(1, severe=2, duration=6100)),
        (option(0, high=1), option(1, high=2)),
        (option(0, moderate=1), option(1, moderate=2)),
        (option(0, duration=600), option(1, duration=660)),
        (option(0), option(1, no_travel=1)),
    )
    codes = {f.code for inputs in scenarios for f in recommend_routes(inputs).explanation_facts}
    assert codes == set(ExplanationCode)
