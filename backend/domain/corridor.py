"""Pure route-chainage corridor sampling and inverse provider-anchor timing."""

from bisect import bisect_right
from collections.abc import Sequence
from fractions import Fraction

from domain.geometry import interpolate_coordinate
from domain.route_types import Checkpoint, Coordinate, Route

OPTIONAL_SPACING_MILES = 10
FRAME_COUNT = 49
FRAME_SECONDS = 3600


def corridor_samples(
    route: Route, checkpoints: Sequence[Checkpoint]
) -> tuple[tuple[Fraction, Coordinate], ...]:
    """Ten-mile interior stations, omitting exact mandatory checkpoint stations."""
    mandatory = {cp.distance_m for cp in checkpoints}
    step = OPTIONAL_SPACING_MILES * route.policy.meters_per_mile
    return tuple(
        (distance, interpolate_coordinate(route, distance))
        for index in range(1, int(route.distance_m // step) + 1)
        if (distance := index * step) < route.distance_m and distance not in mandatory
    )


def truck_position(route: Route, elapsed_s: Fraction) -> tuple[float, float, float] | None:
    """Invert sparse elapsed-time anchors; waits stay stationary, arrival is retained."""
    if elapsed_s > route.duration_s:
        return None
    if elapsed_s == 0:
        origin = route.geometry[0]
        return origin.latitude, origin.longitude, 0.0
    anchors = route.timing_anchors
    index = bisect_right(tuple(a.elapsed_s for a in anchors), elapsed_s) - 1
    a = anchors[max(0, index)]
    distance = a.distance_m
    if index < len(anchors) - 1:
        b = anchors[index + 1]
        if b.elapsed_s > a.elapsed_s:
            distance += (
                (b.distance_m - a.distance_m)
                * (elapsed_s - a.elapsed_s)
                / (b.elapsed_s - a.elapsed_s)
            )
    point = interpolate_coordinate(route, distance)
    return point.latitude, point.longitude, float(distance / route.policy.meters_per_mile)
