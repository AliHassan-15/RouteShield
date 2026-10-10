"""D07/D08 eligibility, exact lexicographic ranking and auditable explanations."""

from collections.abc import Sequence
from dataclasses import replace
from fractions import Fraction
from types import MappingProxyType

from domain.aggregation import TravelStatus
from domain.explanations import render_explanation
from domain.identity import stable_route_id
from domain.recommendation_types import (
    ComparisonCriterion,
    ComparisonFact,
    CriterionValues,
    DecisionCriterion,
    ExplanationCode,
    ExplanationFact,
    ExplanationValue,
    RankedRoute,
    RankingGroup,
    RankingInput,
    Recommendation,
    RecommendationStatus,
)
from domain.risk_types import RiskLevel
from domain.route_types import RouteError

# Presentation policy only: include an exact <=4-minute difference when time
# is lower priority than the criterion that actually decides a comparison.
LOWER_PRIORITY_DURATION_CLOSE_SECONDS = Fraction(240)

STATUS_MESSAGES = MappingProxyType(
    {
        RecommendationStatus.RECOMMENDED: "Recommended fully assessed route",
        RecommendationStatus.BEST_FULLY_ASSESSED_AVAILABLE: "Best fully assessed available route",
        RecommendationStatus.ALL_BLOCKED: "No safe route at this departure time and load",
        RecommendationStatus.NO_FULLY_ASSESSED_TRAVELABLE_ROUTE: (
            "No fully assessed travelable route"
        ),
        RecommendationStatus.ALL_INCOMPLETE: "All routes have incomplete weather data",
    }
)

type AssessedKey = tuple[Fraction, Fraction, Fraction, Fraction, str]
type BlockedKey = tuple[Fraction, Fraction, Fraction, Fraction, Fraction, str]


def _row(item: RankingInput) -> RankedRoute:
    summary = item.summary
    values = CriterionValues(
        summary.no_travel_miles,
        summary.miles_by_level[RiskLevel.SEVERE],
        summary.miles_by_level[RiskLevel.HIGH],
        summary.average_risk,
        summary.total_duration_s,
        stable_route_id(item.route),
    )
    # Consume the aggregation contract, rather than reconstructing its means,
    # category partition or known-block evidence here.
    required = (
        values.no_travel_miles,
        values.severe_miles,
        values.high_miles,
        values.duration_seconds,
        summary.unknown_miles,
        summary.coverage_fraction,
    )
    complete = summary.unknown_miles == 0
    if (
        any(not isinstance(v, Fraction) or v < 0 for v in required)
        or not 0 <= summary.coverage_fraction <= 1
        or values.duration_seconds <= 0
        or complete != (summary.coverage_fraction == 1)
        or complete != (values.average_risk is not None)
        or (
            values.average_risk is not None
            and (not isinstance(values.average_risk, Fraction) or not 1 <= values.average_risk <= 5)
        )
        or (summary.travel_status is TravelStatus.BLOCKED) != summary.known_blocked
        or (
            not summary.known_blocked
            and summary.travel_status
            is not (TravelStatus.ASSESSED if complete else TravelStatus.INCOMPLETE)
        )
    ):
        raise RouteError("INVALID_ROUTE_SUMMARY", "Ranking requires valid exact route aggregates.")
    group = (
        RankingGroup.UNRANKED
        if not complete
        else (RankingGroup.BLOCKED_COMPLETE if summary.known_blocked else RankingGroup.ASSESSED)
    )
    return RankedRoute(
        values.stable_route_id,
        group,
        None,
        summary.travel_status,
        summary.known_blocked,
        values,
        summary.unknown_miles,
        summary.coverage_fraction,
    )


def _assessed_key(row: RankedRoute) -> AssessedKey:
    values = row.criteria
    if values.average_risk is None:
        raise RouteError("INCOMPLETE_AVERAGE", "Incomplete averages cannot be ranked.")
    return (
        values.severe_miles,
        values.high_miles,
        values.average_risk,
        values.duration_seconds,
        values.stable_route_id,
    )


def _blocked_key(row: RankedRoute) -> BlockedKey:
    return (row.criteria.no_travel_miles, *_assessed_key(row))


def _comparison(winner: RankedRoute, other: RankedRoute) -> ComparisonFact:
    if other.group is RankingGroup.UNRANKED or winner.group is not other.group:
        code = (
            ExplanationCode.INCOMPLETE_UNRANKED
            if other.group is RankingGroup.UNRANKED
            else ExplanationCode.ASSESSED_BEFORE_BLOCKED
        )
        return ComparisonFact(
            winner.route_id,
            other.route_id,
            ComparisonCriterion.ELIGIBILITY,
            winner.group.value,
            other.group.value,
            code,
        )
    criteria: tuple[
        tuple[ComparisonCriterion, Fraction | str | None, Fraction | str | None], ...
    ] = (
        (
            ComparisonCriterion.SEVERE_MILES,
            winner.criteria.severe_miles,
            other.criteria.severe_miles,
        ),
        (ComparisonCriterion.HIGH_MILES, winner.criteria.high_miles, other.criteria.high_miles),
        (
            ComparisonCriterion.AVERAGE_RISK,
            winner.criteria.average_risk,
            other.criteria.average_risk,
        ),
        (
            ComparisonCriterion.DURATION,
            winner.criteria.duration_seconds,
            other.criteria.duration_seconds,
        ),
        (ComparisonCriterion.TIE_BROKEN_BY_ID, winner.route_id, other.route_id),
    )
    if winner.group is RankingGroup.BLOCKED_COMPLETE:
        criteria = (
            (
                ComparisonCriterion.NO_TRAVEL_MILES,
                winner.criteria.no_travel_miles,
                other.criteria.no_travel_miles,
            ),
            *criteria,
        )
    for criterion, winning_value, other_value in criteria:
        if winning_value != other_value:
            assert winning_value is not None and other_value is not None
            return ComparisonFact(
                winner.route_id,
                other.route_id,
                criterion,
                winning_value,
                other_value,
                ExplanationCode(criterion.value),
            )
    raise RouteError("DUPLICATE_ROUTE_ID", "Routes must have distinct canonical geometry IDs.")


def _fact(
    code: ExplanationCode,
    route_id: str | None = None,
    other_route_id: str | None = None,
    **values: ExplanationValue,
) -> ExplanationFact:
    return ExplanationFact(code, route_id, other_route_id, MappingProxyType(values))


def recommend_routes(inputs: Sequence[RankingInput]) -> Recommendation:
    """Rank complete routes; UNRANKED rows are ID-ordered for stable presentation.

    Ranks are one-based across ASSESSED then BLOCKED_COMPLETE; incomplete rows
    have no rank. Decisive criterion concerns a recommendation and its next
    assessed competitor only. Without one it is NONE. A separate diagnostic
    criterion can include NO_TRAVEL_MILES for complete blocked comparisons.
    Comparison facts use the recommended route, or the explicitly least-blocked
    diagnostic when no eligible route exists; eligibility exclusions never use
    incomplete averages. Duplicate quantized geometry IDs fail explicitly.
    """
    if not inputs:
        raise RouteError("NO_ROUTE", "At least one route is required for ranking.")
    rows = tuple(_row(item) for item in inputs)
    if len({row.route_id for row in rows}) != len(rows):
        raise RouteError("DUPLICATE_ROUTE_ID", "Routes must have distinct canonical geometry IDs.")
    assessed = sorted((r for r in rows if r.group is RankingGroup.ASSESSED), key=_assessed_key)
    blocked = sorted(
        (r for r in rows if r.group is RankingGroup.BLOCKED_COMPLETE), key=_blocked_key
    )
    incomplete = sorted(
        (r for r in rows if r.group is RankingGroup.UNRANKED), key=lambda r: r.route_id
    )
    ranked = tuple(replace(r, rank=i) for i, r in enumerate((*assessed, *blocked), 1))
    ordered = (*ranked, *incomplete)
    recommended = assessed[0] if assessed else None
    # A diagnostic is exposed only when there is no eligible recommendation.
    diagnostic = blocked[0] if blocked and recommended is None else None
    if recommended is not None:
        status = (
            RecommendationStatus.BEST_FULLY_ASSESSED_AVAILABLE
            if len(assessed) == 1
            else RecommendationStatus.RECOMMENDED
        )
    elif all(r.known_blocked for r in rows):
        status = RecommendationStatus.ALL_BLOCKED
    elif len(incomplete) == len(rows) and not any(r.known_blocked for r in rows):
        status = RecommendationStatus.ALL_INCOMPLETE
    else:
        status = RecommendationStatus.NO_FULLY_ASSESSED_TRAVELABLE_ROUTE
    chosen = recommended or diagnostic
    comparisons = (
        tuple(_comparison(chosen, r) for r in ordered if r.route_id != chosen.route_id)
        if chosen is not None
        else ()
    )
    decisive = (
        DecisionCriterion(_comparison(recommended, assessed[1]).criterion.value)
        if recommended is not None and len(assessed) > 1
        else DecisionCriterion.NONE
    )
    diagnostic_decisive = (
        _comparison(diagnostic, blocked[1]).criterion
        if diagnostic is not None and len(blocked) > 1
        else None
    )
    facts = [_fact(ExplanationCode(status.value), recommended.route_id if recommended else None)]
    if len(rows) < 3:
        facts.append(_fact(ExplanationCode.PARTIAL_ROUTES, route_count=len(rows)))
    if diagnostic is not None:
        facts.append(_fact(ExplanationCode.LEAST_BLOCKED_DIAGNOSTIC, diagnostic.route_id))
    for comparison in comparisons:
        other = next(r for r in ordered if r.route_id == comparison.other_route_id)
        if comparison.code is ExplanationCode.INCOMPLETE_UNRANKED:
            continue  # Every incomplete row is disclosed once below, even with no chosen route.
        facts.append(
            _fact(
                comparison.code,
                comparison.winner_route_id,
                comparison.other_route_id,
                winner_value=comparison.winner_value,
                other_value=comparison.other_value,
            )
        )
        if comparison.criterion in (
            ComparisonCriterion.NO_TRAVEL_MILES,
            ComparisonCriterion.SEVERE_MILES,
            ComparisonCriterion.HIGH_MILES,
            ComparisonCriterion.AVERAGE_RISK,
        ):
            assert chosen is not None
            difference = abs(chosen.criteria.duration_seconds - other.criteria.duration_seconds)
            if 0 < difference <= LOWER_PRIORITY_DURATION_CLOSE_SECONDS:
                facts.append(
                    _fact(
                        ExplanationCode.LOWER_PRIORITY_DURATION_CLOSE,
                        chosen.route_id,
                        other.route_id,
                        duration_difference_seconds=difference,
                    )
                )
    facts.extend(
        _fact(
            ExplanationCode.INCOMPLETE_UNRANKED,
            other_route_id=r.route_id,
            coverage_fraction=r.coverage_fraction,
            unknown_miles=r.unknown_miles,
            known_blocked=r.known_blocked,
        )
        for r in incomplete
    )
    explanation_facts = tuple(facts)
    return Recommendation(
        ordered,
        len(rows),
        recommended.route_id if recommended else None,
        diagnostic.route_id if diagnostic else None,
        status,
        STATUS_MESSAGES[status],
        decisive,
        diagnostic_decisive,
        comparisons,
        explanation_facts,
        render_explanation(explanation_facts),
    )
