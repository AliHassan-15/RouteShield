"""Common interval planning, calibrated checkpoints, UTC ETAs and exact ownership."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from math import ceil
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from domain.geometry import elapsed_at, interpolate_coordinate
from domain.route_policy import DEFAULT_ROUTE_POLICY, RoutePolicy
from domain.route_types import (
    Checkpoint,
    IntervalPlan,
    IntervalWarning,
    LocalCheckpoint,
    Ownership,
    Route,
    RouteCheckpoints,
    RouteError,
    RouteNumber,
    TripCheckpoints,
    exact_number,
)


def midpoint_ownership(
    distances_m: Sequence[RouteNumber],
    total_distance_m: RouteNumber,
    policy: RoutePolicy = DEFAULT_ROUTE_POLICY,
) -> tuple[Ownership, ...]:
    """Partition [0,L] at adjacent midpoints using exact rational arithmetic."""
    total = exact_number(total_distance_m, "route distance")
    positions = tuple(exact_number(value, "checkpoint distance") for value in distances_m)
    if (
        total <= 0
        or len(positions) < 2
        or positions[0] != 0
        or positions[-1] != total
        or any(b <= a for a, b in zip(positions, positions[1:], strict=False))
    ):
        raise RouteError(
            "INVALID_CHECKPOINTS", "Checkpoint distances must increase from zero to route length."
        )
    boundaries = (
        Fraction(0),
        *((a + b) / 2 for a, b in zip(positions, positions[1:], strict=False)),
        total,
    )
    return tuple(
        Ownership(a / policy.meters_per_mile, b / policy.meters_per_mile)
        for a, b in zip(boundaries, boundaries[1:], strict=False)
    )


def _validate_interval(interval: int, policy: RoutePolicy) -> None:
    if type(interval) is not int or interval not in policy.offered_intervals_miles:
        raise RouteError(
            "INVALID_INTERVAL", "Choose one of the policy's offered checkpoint intervals."
        )


def checkpoint_count(route: Route, interval_miles: int) -> int:
    """Count mandatory endpoints and interior samples before allocating coordinates."""
    _validate_interval(interval_miles, route.policy)
    return ceil(route.distance_m / (interval_miles * route.policy.meters_per_mile)) + 1


def select_interval(
    routes: Sequence[Route],
    requested_interval_miles: int | None = None,
    *,
    policy: RoutePolicy | None = None,
) -> IntervalPlan:
    """Use longest accepted route; count per-route points without cross-route dedupe.

    This conservative upper bound precedes the later weather pooling task's 100 m
    deduplication. Each upward step warns, including a user's overridden choice.
    """
    if not routes:
        raise RouteError("NO_ROUTES", "At least one accepted route is required.")
    selected_policy = policy if policy is not None else routes[0].policy
    if any(route.policy != selected_policy for route in routes):
        raise RouteError("POLICY_MISMATCH", "All trip routes must share the same route policy.")
    intervals = selected_policy.offered_intervals_miles
    if requested_interval_miles is not None:
        _validate_interval(requested_interval_miles, selected_policy)
        interval = requested_interval_miles
    else:
        longest = max(route.distance_miles for route in routes)
        interval = intervals[-1]
        for threshold, offered in zip(
            selected_policy.adaptive_thresholds_miles, intervals, strict=False
        ):
            if longest <= threshold:
                interval = offered
                break
    warnings: list[IntervalWarning] = []
    for candidate in intervals[intervals.index(interval) :]:
        if candidate != interval:
            warnings.append(IntervalWarning("CHECKPOINT_INTERVAL_INCREASED", interval, candidate))
            interval = candidate
        count = sum(checkpoint_count(route, interval) for route in routes)
        if count <= selected_policy.checkpoint_budget:
            return IntervalPlan(interval, count, tuple(warnings))
    raise RouteError(
        "TRIP_TOO_LARGE", "Mandatory checkpoints exceed the budget at the largest offered interval."
    )


def utc_departure(departure: datetime) -> datetime:
    """Reject naive/nonexistent named-zone instants, then normalize an actual instant."""
    if not isinstance(departure, datetime) or departure.utcoffset() is None:
        raise RouteError("NAIVE_DEPARTURE", "Departure must be a timezone-aware datetime.")
    utc = departure.astimezone(UTC)
    if isinstance(departure.tzinfo, ZoneInfo) and (
        utc.astimezone(departure.tzinfo).replace(tzinfo=None) != departure.replace(tzinfo=None)
    ):
        raise RouteError(
            "NONEXISTENT_DEPARTURE", "Departure wall time does not exist in its IANA zone."
        )
    return utc


def generate_checkpoints(
    route: Route, departure: datetime, interval_miles: int, *, check_budget: bool = True
) -> tuple[Checkpoint, ...]:
    """Generate a bounded route at an already selected interval, including both ends."""
    utc = utc_departure(departure)
    count = checkpoint_count(route, interval_miles)
    if check_budget and count > route.policy.checkpoint_budget:
        raise RouteError(
            "TRIP_TOO_LARGE", "Select a coarser permitted interval before generating checkpoints."
        )
    spacing = interval_miles * route.policy.meters_per_mile
    distances = (Fraction(0), *(spacing * i for i in range(1, count - 1)), route.distance_m)
    ownership = midpoint_ownership(distances, route.distance_m, route.policy)
    result: list[Checkpoint] = []
    for distance, owned in zip(distances, ownership, strict=True):
        elapsed = elapsed_at(route, distance)
        try:
            # datetime has microsecond resolution; exact seconds remain on the object.
            eta = utc + timedelta(microseconds=round(elapsed * 1_000_000))
        except OverflowError as error:
            raise RouteError(
                "ETA_OUT_OF_RANGE", "Provider duration exceeds datetime's supported range."
            ) from error
        result.append(
            Checkpoint(interpolate_coordinate(route, distance), distance, elapsed, eta, owned)
        )
    return tuple(result)


def candidate_intervals(routes: Sequence[Route], requested: int | None = None) -> tuple[int, ...]:
    """Offer the common adaptive interval and coarser options before unique pooling.

    The API must evaluate actual pooled coordinates, rather than select_interval's
    historical conservative pre-deduplication count. No provider imports belong here.
    """
    if not routes:
        raise RouteError("NO_ROUTE", "At least one route is required.")
    policy = routes[0].policy
    if any(route.policy != policy for route in routes):
        raise RouteError("POLICY_MISMATCH", "All trip routes must share a policy.")
    offered = policy.offered_intervals_miles
    if requested is not None:
        _validate_interval(requested, policy)
        initial = requested
    else:
        longest = max(route.distance_miles for route in routes)
        initial = offered[-1]
        for threshold, interval in zip(policy.adaptive_thresholds_miles, offered, strict=False):
            if longest <= threshold:
                initial = interval
                break
    return offered[offered.index(initial) :]


def generate_trip_checkpoints(
    routes: Sequence[Route],
    departure: datetime,
    requested_interval_miles: int | None = None,
    *,
    policy: RoutePolicy | None = None,
) -> TripCheckpoints:
    """Apply one announced interval plan to every already accepted trip route."""
    plan = select_interval(routes, requested_interval_miles, policy=policy)
    return TripCheckpoints(
        plan,
        tuple(
            RouteCheckpoints(route, generate_checkpoints(route, departure, plan.interval_miles))
            for route in routes
        ),
    )


def attach_timezone(checkpoint: Checkpoint, timezone_name: str | None) -> LocalCheckpoint:
    """Attach checkpoint-specific IANA display time with explicit missing/invalid fallback."""
    utc = utc_departure(checkpoint.eta_utc)
    warning: str | None = None
    if not timezone_name:
        warning = "MISSING_TIMEZONE_UTC_FALLBACK"
    try:
        zone = ZoneInfo(timezone_name) if timezone_name else UTC
    except (ZoneInfoNotFoundError, ValueError):
        zone = UTC
        warning = "INVALID_TIMEZONE_UTC_FALLBACK"
    return LocalCheckpoint(
        checkpoint,
        (timezone_name or "UTC") if warning is None else "UTC",
        utc.astimezone(zone),
        warning is not None,
        warning,
    )
