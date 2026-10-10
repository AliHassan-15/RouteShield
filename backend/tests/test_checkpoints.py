"""CP-01..06/MET-01: exact spacing, budgets, ownership and actual UTC instants."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from fractions import Fraction
from zoneinfo import ZoneInfo

import pytest
from domain.checkpoints import (
    attach_timezone,
    checkpoint_count,
    generate_checkpoints,
    generate_trip_checkpoints,
    midpoint_ownership,
    select_interval,
)
from domain.route_policy import DEFAULT_ROUTE_POLICY, RoutePolicy
from domain.route_types import RouteError, RouteNumber

from tests.route_helpers import straight_route

F = Fraction
DEPARTURE = datetime(2026, 10, 10, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    "length,positions,owned",
    [
        (100, (0, 25, 50, 75, 100), ("12.5", "25", "25", "25", "12.5")),
        (105, (0, 25, 50, 75, 100, 105), ("12.5", "25", "25", "25", "15", "2.5")),
    ],
)
def test_golden_midpoint_cases(
    length: int, positions: tuple[int, ...], owned: tuple[str, ...]
) -> None:
    """Golden A/B: the final 5 mi is split into 2.5 mi for each neighboring checkpoint."""
    route = straight_route(length)
    checkpoints = generate_checkpoints(route, DEPARTURE, 25)
    assert tuple(c.distance_m / route.policy.meters_per_mile for c in checkpoints) == positions
    assert tuple(c.owned_miles for c in checkpoints) == tuple(F(value) for value in owned)
    assert sum(c.owned_miles for c in checkpoints) == length
    if length == 105:
        assert (
            checkpoints[0].ownership.start_miles,
            *(c.ownership.end_miles for c in checkpoints),
        ) == tuple(F(value) for value in ("0", "12.5", "37.5", "62.5", "87.5", "102.5", "105"))


@pytest.mark.parametrize(
    "length,positions,owned",
    [
        (5, (0, 5), ("2.5", "2.5")),
        (10, (0, 10), ("5", "5")),
        (20, (0, 10, 20), ("5", "10", "5")),
        (23, (0, 10, 20, 23), ("5", "10", "6.5", "1.5")),
    ],
)
def test_short_exact_and_partial_final_intervals(
    length: int,
    positions: tuple[int, ...],
    owned: tuple[str, ...],
) -> None:
    route = straight_route(length)
    checkpoints = generate_checkpoints(route, DEPARTURE, 10)
    assert tuple(c.distance_m / route.policy.meters_per_mile for c in checkpoints) == positions
    assert tuple(c.owned_miles for c in checkpoints) == tuple(F(value) for value in owned)
    assert checkpoints[0].coordinate == route.geometry[0]
    assert checkpoints[-1].coordinate == route.geometry[-1]


@pytest.mark.parametrize(
    "interval,positions",
    [
        (10, (0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 105)),
        (25, (0, 25, 50, 75, 100, 105)),
        (50, (0, 50, 100, 105)),
    ],
)
def test_all_offered_intervals_on_same_route(interval: int, positions: tuple[int, ...]) -> None:
    route = straight_route(105)
    checkpoints = generate_checkpoints(route, DEPARTURE, interval)
    assert tuple(c.distance_m / route.policy.meters_per_mile for c in checkpoints) == positions
    assert checkpoint_count(route, interval) == len(checkpoints)
    assert sum(c.owned_miles for c in checkpoints) == 105


@pytest.mark.parametrize(
    "longest,expected", [("100", 10), ("100.0001", 25), ("500", 25), ("500.0001", 50)]
)
def test_adaptive_default_uses_longest_route_in_any_order(longest: str, expected: int) -> None:
    routes = (straight_route(5), straight_route(longest), straight_route(50))
    for candidates in (routes, tuple(reversed(routes))):
        assert select_interval(candidates).interval_miles == expected


@pytest.mark.parametrize("choice", [10, 25, 50])
def test_user_selection_and_common_trip_interval(choice: int) -> None:
    routes = (straight_route(5), straight_route(105), straight_route(300))
    result = generate_trip_checkpoints(routes, DEPARTURE, choice)
    assert result.plan.interval_miles == choice and result.plan.warnings == ()
    assert result.plan.checkpoint_count == sum(len(value.checkpoints) for value in result.routes)
    for values in result.routes:
        assert len(values.checkpoints) == checkpoint_count(values.route, choice)


@pytest.mark.parametrize(
    "length,new_interval,steps,count",
    [
        (1000, 25, ((10, 25),), 123),  # 3*101=303 >300, then3*41=123
        (2500, 50, ((10, 25), (25, 50)), 153),  # 753 ->303 ->153
    ],
)
def test_budget_warns_for_every_upward_step(
    length: int,
    new_interval: int,
    steps: tuple[tuple[int, int], ...],
    count: int,
) -> None:
    route = straight_route(length)
    plan = select_interval((route, route, route), 10)
    assert plan.interval_miles == new_interval and plan.checkpoint_count == count
    assert tuple((w.old_interval_miles, w.new_interval_miles) for w in plan.warnings) == steps
    assert all(w.code == "CHECKPOINT_INTERVAL_INCREASED" for w in plan.warnings)


def test_budget_counts_each_route_before_later_weather_deduplication() -> None:
    """Three identical inputs still reserve 303 mandatory points at10, not101 pooled points."""
    route = straight_route(1000)
    assert select_interval((route, route, route), 10).interval_miles == 25


def test_trip_too_large_at_largest_offered_interval() -> None:
    """Three5000mi routes need 3*101=303 at50mi, beyond the frozen300 budget."""
    route = straight_route(5000)
    for selected in (None, 10, 25, 50):
        with pytest.raises(RouteError) as error:
            select_interval((route, route, route), selected)
        assert error.value.code == "TRIP_TOO_LARGE"


def test_all_sampling_values_are_policy_parameters() -> None:
    policy = RoutePolicy(
        offered_intervals_miles=(5, 20, 60),
        adaptive_thresholds_miles=(F(20), F(200)),
        checkpoint_budget=6,
        meters_per_mile=F(1000),
    )
    route = straight_route(40, policy=policy)
    plan = select_interval((route,), 5, policy=policy)
    assert plan.interval_miles == 20 and plan.checkpoint_count == 3
    assert plan.warnings[0].old_interval_miles == 5
    assert select_interval((route,)).interval_miles == 20
    points = generate_checkpoints(route, DEPARTURE, 20)
    assert tuple(c.distance_m for c in points) == (F(0), F(20000), F(40000))
    assert sum(c.owned_miles for c in points) == 40


def test_configurable_budget_retains_frozen_default() -> None:
    policy = replace(DEFAULT_ROUTE_POLICY, checkpoint_budget=100)
    route = straight_route(1000, policy=policy)
    assert select_interval((route, route, route), 10).interval_miles == 50
    assert DEFAULT_ROUTE_POLICY.checkpoint_budget == 300


@pytest.mark.parametrize("interval", [-1, 0, 15, 100, True, 10.0])
def test_unoffered_or_malformed_interval_rejected(interval: int) -> None:
    route = straight_route(20)
    for action in (
        lambda: select_interval((route,), interval),
        lambda: generate_checkpoints(route, DEPARTURE, interval),
    ):
        with pytest.raises(RouteError) as error:
            action()
        assert error.value.code == "INVALID_INTERVAL"


def test_missing_routes_and_mismatched_policies_are_clear_errors() -> None:
    with pytest.raises(RouteError) as error:
        select_interval(())
    assert error.value.code == "NO_ROUTES"
    altered = replace(DEFAULT_ROUTE_POLICY, checkpoint_budget=100)
    with pytest.raises(RouteError) as error:
        select_interval((straight_route(10), straight_route(10, policy=altered)))
    assert error.value.code == "POLICY_MISMATCH"


@pytest.mark.parametrize(
    "length",
    [
        ".00000000000001",
        "1.234567890123456789012345678901",
        "5",
        "23",
        "99.9999",
        "100",
        "105",
        "199.123456789",
    ],
)
@pytest.mark.parametrize("interval", [10, 25, 50])
def test_exact_conservation_across_generated_routes(length: str, interval: int) -> None:
    """Rational midpoint intervals telescope exactly, including long decimal tails."""
    # Tiny routes below the geometric duplicate tolerance are handled as ownership
    # inputs only; pretending they contain two distinguishable road points is invalid.
    total = F(length) * DEFAULT_ROUTE_POLICY.meters_per_mile
    spacing = interval * DEFAULT_ROUTE_POLICY.meters_per_mile
    positions = [F(0)]
    while positions[-1] + spacing < total:
        positions.append(positions[-1] + spacing)
    positions.append(total)
    ownership = midpoint_ownership(positions, total)
    assert sum(value.owned_miles for value in ownership) == F(length)
    if F(length) >= 1:
        route = straight_route(length)
        assert (
            sum(c.owned_miles for c in generate_checkpoints(route, DEPARTURE, interval))
            == route.distance_miles
        )
    for precision in (2, 28, 60):
        with localcontext() as context:
            context.prec = precision
            assert midpoint_ownership(positions, total) == ownership


def test_exact_meters_per_mile_and_decimal_inputs() -> None:
    """One mile is exactly1609.344 m; Decimal context cannot alter rational conversion."""
    assert DEFAULT_ROUTE_POLICY.meters_per_mile == F(201168, 125)
    values = (Decimal("0"), Decimal("1609.344"))
    ownership = midpoint_ownership(values, Decimal("1609.344"))
    assert tuple(value.owned_miles for value in ownership) == (F(1, 2), F(1, 2))


@pytest.mark.parametrize(
    "positions,total",
    [
        ((0, 10, 5), 5),
        ((1, 10), 10),
        ((0, 9), 10),
        ((0, 0, 10), 10),
        ((0,), 10),
        ((0, 10), 0),
        ((0, float("nan")), 10),
        ((False, 10), 10),
    ],
)
def test_invalid_ownership_inputs(positions: tuple[RouteNumber, ...], total: RouteNumber) -> None:
    with pytest.raises(RouteError):
        midpoint_ownership(positions, total)


def test_timezone_offset_midnight_and_nonuniform_etas() -> None:
    departure = datetime(2026, 10, 10, 23, 55, tzinfo=timezone(timedelta(hours=-5)))
    route = straight_route(20, positions_miles=(0, 10, 20), times_s=(0, 600, 1800))
    checkpoints = generate_checkpoints(route, departure, 10)
    assert tuple(c.eta_utc for c in checkpoints) == tuple(
        datetime(2026, 10, 11, 4, 55, tzinfo=UTC) + timedelta(seconds=s) for s in (0, 600, 1800)
    )
    assert all(c.eta_utc.tzinfo is UTC for c in checkpoints)
    assert all(b.eta_utc >= a.eta_utc for a, b in zip(checkpoints, checkpoints[1:], strict=False))
    west = attach_timezone(checkpoints[0], "America/Los_Angeles")
    east = attach_timezone(checkpoints[-1], "America/New_York")
    assert west.local_time.utcoffset() != east.local_time.utcoffset()
    assert west.local_time.astimezone(UTC) == checkpoints[0].eta_utc


def test_dst_crossing_changes_local_offset_without_changing_elapsed() -> None:
    """Spring1:55 EST plus30min becomes3:25 EDT, not2:25 with a fixed trip offset."""
    route = straight_route(20, positions_miles=(0, 10, 20), times_s=(0, 600, 1800))
    departure = datetime(2026, 3, 8, 1, 55, tzinfo=ZoneInfo("America/New_York"))
    checkpoints = generate_checkpoints(route, departure, 10)
    end = attach_timezone(checkpoints[-1], "America/New_York")
    assert (end.local_time.hour, end.local_time.minute) == (3, 25)
    assert end.local_time.utcoffset() == timedelta(hours=-4)
    assert checkpoints[-1].eta_utc - checkpoints[0].eta_utc == timedelta(seconds=1800)


@pytest.mark.parametrize("fold,expected_hour", [(0, 5), (1, 6)])
def test_dst_repeat_preserves_selected_instant(fold: int, expected_hour: int) -> None:
    departure = datetime(2026, 11, 1, 1, 30, tzinfo=ZoneInfo("America/New_York"), fold=fold)
    origin = generate_checkpoints(straight_route(5), departure, 50)[0]
    assert origin.eta_utc.hour == expected_hour


@pytest.mark.parametrize(
    "name,code",
    [
        (None, "MISSING_TIMEZONE_UTC_FALLBACK"),
        ("", "MISSING_TIMEZONE_UTC_FALLBACK"),
        ("No/Such_Zone", "INVALID_TIMEZONE_UTC_FALLBACK"),
        ("../bad", "INVALID_TIMEZONE_UTC_FALLBACK"),
    ],
)
def test_explicit_utc_fallback(name: str | None, code: str) -> None:
    checkpoint = generate_checkpoints(straight_route(5), DEPARTURE, 50)[0]
    display = attach_timezone(checkpoint, name)
    assert display.timezone_name == "UTC" and display.used_utc_fallback
    assert display.warning_code == code and display.local_time == checkpoint.eta_utc


@pytest.mark.parametrize(
    "departure,code",
    [
        (datetime(2026, 10, 10, 12), "NAIVE_DEPARTURE"),
        (datetime(2026, 3, 8, 2, 30, tzinfo=ZoneInfo("America/New_York")), "NONEXISTENT_DEPARTURE"),
    ],
)
def test_naive_and_nonexistent_departures_rejected(departure: datetime, code: str) -> None:
    with pytest.raises(RouteError) as error:
        generate_checkpoints(straight_route(5), departure, 10)
    assert error.value.code == code


def test_checkpoint_values_are_immutable() -> None:
    checkpoint = generate_checkpoints(straight_route(5), DEPARTURE, 50)[0]
    for target, name, value in (
        (checkpoint, "elapsed_s", F(100)),
        (checkpoint.ownership, "end_miles", F(100)),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(target, name, value)
    # A manually malformed checkpoint cannot make local display depend on machine timezone.
    with pytest.raises(RouteError):
        attach_timezone(replace(checkpoint, eta_utc=DEPARTURE.replace(tzinfo=None)), "UTC")


@pytest.mark.parametrize(
    "changes",
    [
        {"offered_intervals_miles": (10, 10, 50)},
        {"offered_intervals_miles": (50, 25, 10)},
        {"offered_intervals_miles": (0, 25, 50)},
        {"checkpoint_budget": True},
        {"checkpoint_budget": 1},
        {"adaptive_thresholds_miles": (F(500), F(100))},
        {"meters_per_mile": F(0)},
        {"geometry_relative_tolerance": F(-1)},
        {"antipodal_tolerance_radians": float("nan")},
    ],
)
def test_invalid_policies_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        # These deliberately malformed runtime configurations violate the static types.
        replace(DEFAULT_ROUTE_POLICY, **changes)  # type: ignore[arg-type]


def test_direct_generation_is_bounded_before_allocating_points() -> None:
    with pytest.raises(RouteError) as error:
        generate_checkpoints(straight_route(5000), DEPARTURE, 10)
    assert error.value.code == "TRIP_TOO_LARGE"
