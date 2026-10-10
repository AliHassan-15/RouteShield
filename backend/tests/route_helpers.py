"""Small synthetic normalized routes; no live/provider implementation code."""

from collections.abc import Sequence
from fractions import Fraction
from math import degrees

from domain.geometry import build_route
from domain.route_policy import DEFAULT_ROUTE_POLICY, RoutePolicy
from domain.route_types import Coordinate, Route, TimingAnchor


def anchor(index: int, distance: str | int | Fraction, time: str | int | Fraction) -> TimingAnchor:
    """Supply exact normalized anchor values for hand-calculated test scenarios."""
    return TimingAnchor(index, Fraction(distance), Fraction(time))


def straight_route(
    miles: str | int | Fraction,
    *,
    policy: RoutePolicy = DEFAULT_ROUTE_POLICY,
    positions_miles: Sequence[str | int | Fraction] | None = None,
    times_s: Sequence[str | int | Fraction] | None = None,
) -> Route:
    """Equatorial minor-arc route with exact provider miles and explicit vertex timing."""
    positions = tuple(Fraction(value) for value in (positions_miles or (0, miles)))
    distances = tuple(value * policy.meters_per_mile for value in positions)
    geometry = tuple(
        Coordinate(degrees(float(distance / policy.earth_radius_m)), 0) for distance in distances
    )
    times = (
        tuple(Fraction(value) for value in times_s)
        if times_s is not None
        else (Fraction(0), Fraction(600))
    )
    return build_route(
        geometry,
        Fraction(miles) * policy.meters_per_mile,
        times[-1],
        cumulative_distances_m=distances,
        cumulative_times_s=times,
        policy=policy,
    )
