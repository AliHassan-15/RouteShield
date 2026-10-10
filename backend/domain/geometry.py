"""Spherical road-polyline geometry calibrated to validated provider chainage.

Coordinates interpolate on the minor great-circle arc, including antimeridian
and polar segments. A near-antipodal pair has no unique stable arc and is rejected.
The spherical distance approximation is reconciled at every timing-anchor span,
not only at the route endpoints. Loops are valid; latitude/longitude need not sort.
"""

from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from fractions import Fraction
from math import atan2, cos, degrees, hypot, pi, radians, sin

from domain.route_policy import DEFAULT_ROUTE_POLICY, RoutePolicy
from domain.route_types import (
    Coordinate,
    Route,
    RouteError,
    RouteNumber,
    TimingAnchor,
    TimingSource,
    TimingWarning,
    exact_number,
)


def _vector(point: Coordinate) -> tuple[float, float, float]:
    lon, lat = radians(point.longitude), radians(point.latitude)
    return cos(lat) * cos(lon), cos(lat) * sin(lon), sin(lat)


def _angle(a: Coordinate, b: Coordinate, policy: RoutePolicy) -> float:
    x, y = _vector(a), _vector(b)
    cross = (x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0])
    angle = atan2(hypot(*cross), sum(u * v for u, v in zip(x, y, strict=True)))
    if pi - angle <= policy.antipodal_tolerance_radians:
        raise RouteError("AMBIGUOUS_SEGMENT", "Near-antipodal geometry has no unique minor arc.")
    return angle


def geometric_chainage(
    geometry: Sequence[Coordinate],
    policy: RoutePolicy = DEFAULT_ROUTE_POLICY,
) -> tuple[Fraction, ...]:
    """Accumulate traveled polyline length, never endpoint distance or vertex count."""
    if (
        not isinstance(geometry, Sequence)
        or len(geometry) < 2
        or any(not isinstance(point, Coordinate) for point in geometry)
    ):
        raise RouteError("INVALID_GEOMETRY", "Geometry needs at least two valid coordinates.")
    values = [Fraction(0)]
    for a, b in zip(geometry, geometry[1:], strict=False):
        distance = exact_number(_angle(a, b, policy) * float(policy.earth_radius_m), "segment")
        # Sub-millimeter coincident points become exact zero; timing is still retained.
        values.append(
            values[-1] + (0 if distance <= policy.duplicate_point_tolerance_m else distance)
        )
    return tuple(values)


def _reconcile(geometric: Fraction, provider: Fraction, policy: RoutePolicy) -> None:
    tolerance = (
        policy.geometry_absolute_tolerance_m + policy.geometry_relative_tolerance * geometric
    )
    if abs(provider - geometric) > tolerance:
        raise RouteError("GEOMETRY_DISTANCE_MISMATCH", "Provider and geometric chainage disagree.")


def _validate_anchors(
    anchors: Sequence[TimingAnchor],
    geometry: tuple[Fraction, ...],
    distance: Fraction,
    duration: Fraction,
    policy: RoutePolicy,
) -> tuple[tuple[TimingAnchor, ...], bool]:
    if (
        not isinstance(anchors, Sequence)
        or len(anchors) < 2
        or any(not isinstance(a, TimingAnchor) for a in anchors)
    ):
        raise RouteError(
            "INVALID_TIMING", "At least two geometry-indexed timing anchors are required."
        )
    normalized = tuple(
        TimingAnchor(
            a.point_index,
            exact_number(a.distance_m, "anchor distance"),
            exact_number(a.elapsed_s, "anchor time"),
        )
        for a in anchors
    )
    for anchor in normalized:
        if (
            type(anchor.point_index) is not int
            or not 0 <= anchor.point_index < len(geometry)
            or anchor.distance_m < 0
            or anchor.elapsed_s < 0
        ):
            raise RouteError(
                "INVALID_TIMING", "Timing indexes and cumulative values must be valid."
            )
    first, last = normalized[0], normalized[-1]
    for a, b in zip(normalized, normalized[1:], strict=False):
        if (
            b.point_index < a.point_index
            or b.distance_m < a.distance_m
            or b.elapsed_s < a.elapsed_s
        ):
            raise RouteError(
                "DECREASING_TIMING", "Timing indexes, distances and times must not decrease."
            )
    if first.point_index != 0 or first.distance_m != 0 or first.elapsed_s != 0:
        raise RouteError(
            "INVALID_TIMING_START", "Timing must start at the origin with distance/time zero."
        )
    if (
        last.point_index != len(geometry) - 1
        or abs(last.distance_m - distance) > policy.distance_endpoint_tolerance_m
        or abs(last.elapsed_s - duration) > policy.time_endpoint_tolerance_s
    ):
        raise RouteError(
            "INVALID_TIMING_END", "Timing must end at the summary distance and duration."
        )
    reconciled = last.distance_m != distance or last.elapsed_s != duration
    normalized = (*normalized[:-1], TimingAnchor(last.point_index, distance, duration))
    for a, b in zip(normalized, normalized[1:], strict=False):
        if (
            b.point_index < a.point_index
            or b.distance_m < a.distance_m
            or b.elapsed_s < a.elapsed_s
        ):
            raise RouteError(
                "DECREASING_TIMING", "Timing indexes, distances and times must not decrease."
            )
        geometric_span = geometry[b.point_index] - geometry[a.point_index]
        provider_span = b.distance_m - a.distance_m
        if geometric_span == 0 and provider_span != 0:
            raise RouteError(
                "UNMAPPABLE_TIMING", "Stationary geometry cannot acquire traveled distance."
            )
        if geometric_span > 0 and provider_span == 0:
            raise RouteError(
                "UNMAPPABLE_TIMING", "Moving geometry needs positive provider chainage."
            )
        _reconcile(geometric_span, provider_span, policy)
    return normalized, reconciled


def _expand(
    anchors: tuple[TimingAnchor, ...],
    geometric: tuple[Fraction, ...],
) -> tuple[tuple[Fraction, ...], tuple[Fraction, ...]]:
    distances: list[Fraction | None] = [None] * len(geometric)
    times: list[Fraction | None] = [None] * len(geometric)
    for a, b in zip(anchors, anchors[1:], strict=False):
        span = geometric[b.point_index] - geometric[a.point_index]
        for index in range(a.point_index, b.point_index + 1):
            fraction = (geometric[index] - geometric[a.point_index]) / span if span else Fraction(1)
            distances[index] = a.distance_m + fraction * (b.distance_m - a.distance_m)
            times[index] = a.elapsed_s + fraction * (b.elapsed_s - a.elapsed_s)
    # An origin wait must not move the origin ETA; the complete anchors keep that wait.
    distances[0], times[0] = Fraction(0), Fraction(0)
    if any(value is None for value in (*distances, *times)):
        raise RouteError("INVALID_TIMING", "Timing anchors leave unmapped geometry vertices.")
    return (
        tuple(value for value in distances if value is not None),
        tuple(value for value in times if value is not None),
    )


def build_route(
    geometry: Sequence[Coordinate],
    distance_m: RouteNumber,
    duration_s: RouteNumber,
    *,
    cumulative_distances_m: Sequence[RouteNumber] | None = None,
    cumulative_times_s: Sequence[RouteNumber] | None = None,
    progress_anchors: Sequence[TimingAnchor] = (),
    guidance_anchors: Sequence[TimingAnchor] = (),
    policy: RoutePolicy = DEFAULT_ROUTE_POLICY,
) -> Route:
    """Validate normalized input, preferring vertex/progress timing then guidance.

    Sparse progress is the actual observed geometry-indexed provider shape.
    It expands into aligned arrays within each real anchor span. Invalid primary
    timing uses valid guidance only, with an explicit source and warning.
    """
    if not isinstance(geometry, Sequence):
        raise RouteError("INVALID_GEOMETRY", "Geometry must be an ordered coordinate sequence.")
    coordinates = tuple(geometry)
    geometric = geometric_chainage(coordinates, policy)
    distance, duration = exact_number(distance_m, "distance"), exact_number(duration_s, "duration")
    if distance <= 0 or duration < 0 or geometric[-1] == 0:
        raise RouteError(
            "INVALID_ROUTE_TOTAL", "Route needs positive traveled distance and nonnegative time."
        )
    _reconcile(geometric[-1], distance, policy)
    source = (
        TimingSource.ALIGNED
        if (cumulative_distances_m is not None or cumulative_times_s is not None)
        else TimingSource.PROGRESS
    )
    warnings: tuple[TimingWarning, ...] = ()
    try:
        if source is TimingSource.ALIGNED:
            if (
                not isinstance(cumulative_distances_m, Sequence)
                or not isinstance(cumulative_times_s, Sequence)
                or len(cumulative_distances_m) != len(coordinates)
                or len(cumulative_times_s) != len(coordinates)
            ):
                raise RouteError(
                    "INVALID_TIMING_LENGTH", "Both cumulative arrays must align to all vertices."
                )
            primary = tuple(
                TimingAnchor(i, exact_number(d, "vertex distance"), exact_number(t, "vertex time"))
                for i, (d, t) in enumerate(
                    zip(cumulative_distances_m, cumulative_times_s, strict=True)
                )
            )
        else:
            if not isinstance(progress_anchors, Sequence):
                raise RouteError(
                    "INVALID_TIMING", "Progress must be a sequence of normalized anchors."
                )
            primary = tuple(progress_anchors)
        anchors, reconciled = _validate_anchors(primary, geometric, distance, duration, policy)
    except RouteError as primary_error:
        if not guidance_anchors:
            raise RouteError(
                "NO_VALID_TIMING", f"No valid provider timing: {primary_error.code}."
            ) from primary_error
        try:
            anchors, reconciled = _validate_anchors(
                guidance_anchors, geometric, distance, duration, policy
            )
        except RouteError as guidance_error:
            raise RouteError(
                "NO_VALID_TIMING", "Neither primary nor guidance timing is valid."
            ) from guidance_error
        source = TimingSource.GUIDANCE
        warnings = (TimingWarning("GUIDANCE_TIMING_FALLBACK", source, primary_error.code),)
    if reconciled:
        warnings += (TimingWarning("TIMING_ENDPOINT_RECONCILED", source),)
    distances, times = _expand(anchors, geometric)
    kept = [0]
    remapped = [0]
    for i in range(1, len(coordinates)):
        if geometric[i] != geometric[kept[-1]]:
            kept.append(i)
        elif i == len(coordinates) - 1:
            kept[-1] = i  # Preserve the actual destination when collapsing its duplicate.
        remapped.append(len(kept) - 1)
    if len(kept) < 2:
        raise RouteError("INVALID_GEOMETRY", "Geometry needs two distinct traveled points.")
    remapped_anchors = tuple(
        TimingAnchor(remapped[a.point_index], a.distance_m, a.elapsed_s) for a in anchors
    )
    collapsed_distances = tuple(distances[i] for i in kept)
    collapsed_time_values = [times[i] for i in kept]
    # A checkpoint ETA is first arrival at an interior vertex; full anchors keep
    # its subsequent wait. Destination elapsed remains the summary duration.
    arrivals: dict[int, Fraction] = {}
    for anchor in remapped_anchors:
        arrivals.setdefault(anchor.point_index, anchor.elapsed_s)
    for index, arrival in arrivals.items():
        collapsed_time_values[index] = arrival
    collapsed_time_values[0] = Fraction(0)
    collapsed_time_values[-1] = duration
    collapsed_times = tuple(collapsed_time_values)
    if any(b <= a for a, b in zip(collapsed_distances, collapsed_distances[1:], strict=False)):
        raise RouteError(
            "UNMAPPABLE_TIMING", "Distinct vertices require increasing traveled chainage."
        )
    return Route(
        tuple(coordinates[i] for i in kept),
        distance,
        duration,
        tuple(geometric[i] for i in kept),
        collapsed_distances,
        collapsed_times,
        remapped_anchors,
        source,
        warnings,
        policy,
    )


def interpolate_coordinate(route: Route, distance_m: Fraction) -> Coordinate:
    """Locate calibrated chainage then interpolate on that segment's spherical arc."""
    distance_m = exact_number(distance_m, "checkpoint chainage")
    if not 0 <= distance_m <= route.distance_m:
        raise RouteError("INVALID_CHAINAGE", "Checkpoint distance must be within the route.")
    if distance_m == route.distance_m:
        return route.geometry[-1]
    index = bisect_right(route.cumulative_distances_m, distance_m) - 1
    a, b = route.geometry[index : index + 2]
    fraction = (distance_m - route.cumulative_distances_m[index]) / (
        route.cumulative_distances_m[index + 1] - route.cumulative_distances_m[index]
    )
    if fraction == 0:
        return a
    angle = _angle(a, b, route.policy)
    x, y = _vector(a), _vector(b)
    f = float(fraction)
    vector = tuple(
        (sin((1 - f) * angle) * u + sin(f * angle) * v) / sin(angle)
        for u, v in zip(x, y, strict=True)
    )
    return Coordinate(
        degrees(atan2(vector[1], vector[0])), degrees(atan2(vector[2], hypot(vector[0], vector[1])))
    )


def elapsed_at(route: Route, distance_m: Fraction) -> Fraction:
    """Interpolate between actual cumulative anchors, retaining stationary waits."""
    distance_m = exact_number(distance_m, "timing chainage")
    if not 0 <= distance_m <= route.distance_m:
        raise RouteError("INVALID_CHAINAGE", "Timing distance must be within the route.")
    if distance_m == 0:
        return Fraction(0)
    if distance_m == route.distance_m:
        return route.duration_s
    anchors = route.timing_anchors
    distances = tuple(a.distance_m for a in anchors)
    first = bisect_left(distances, distance_m)
    if anchors[first].distance_m == distance_m:
        return anchors[first].elapsed_s
    index = bisect_right(distances, distance_m) - 1
    a, b = anchors[index : index + 2]
    fraction = (distance_m - a.distance_m) / (b.distance_m - a.distance_m)
    return a.elapsed_s + fraction * (b.elapsed_s - a.elapsed_s)
