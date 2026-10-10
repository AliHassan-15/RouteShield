"""D04/D21 defaults and explicit numerical reconciliation parameters.

The approved default is 200. Trip selection currently counts points before
pooling; dedupe-aware budgeting belongs to the later corridor integration task.
Geometry uses a mean-radius sphere, whose WGS84 distance error can approach
0.56%. The configurable 1% plus 5 m reconciliation allowance covers that model
and road-polyline rounding; it is an implementation tolerance, not a guarantee.
"""

from dataclasses import dataclass
from fractions import Fraction
from math import isfinite, pi


@dataclass(frozen=True, slots=True)
class RoutePolicy:
    """All adjustable sampling, geometry and timing limits in one value object."""

    offered_intervals_miles: tuple[int, ...] = (10, 25, 50)
    adaptive_thresholds_miles: tuple[Fraction, ...] = (Fraction(100), Fraction(500))
    checkpoint_budget: int = 200
    meters_per_mile: Fraction = Fraction("1609.344")
    earth_radius_m: Fraction = Fraction("6371008.8")
    geometry_absolute_tolerance_m: Fraction = Fraction(5)
    geometry_relative_tolerance: Fraction = Fraction("0.01")
    distance_endpoint_tolerance_m: Fraction = Fraction(1)
    time_endpoint_tolerance_s: Fraction = Fraction(1)
    duplicate_point_tolerance_m: Fraction = Fraction("0.001")
    antipodal_tolerance_radians: float = 1e-9

    def __post_init__(self) -> None:
        """Reject inconsistent policies before processing a route."""
        intervals = self.offered_intervals_miles
        thresholds = self.adaptive_thresholds_miles
        if (
            not isinstance(intervals, tuple)
            or not intervals
            or any(type(value) is not int or value <= 0 for value in intervals)
            or tuple(sorted(set(intervals))) != intervals
            or not isinstance(thresholds, tuple)
            or len(thresholds) != len(intervals) - 1
            or any(not isinstance(value, Fraction) or value <= 0 for value in thresholds)
            or tuple(sorted(set(thresholds))) != thresholds
            or type(self.checkpoint_budget) is not int
            or self.checkpoint_budget < 2
        ):
            raise ValueError("Invalid interval, adaptive threshold or checkpoint budget policy.")
        positive = (self.meters_per_mile, self.earth_radius_m)
        nonnegative = (
            self.geometry_absolute_tolerance_m,
            self.geometry_relative_tolerance,
            self.distance_endpoint_tolerance_m,
            self.time_endpoint_tolerance_s,
            self.duplicate_point_tolerance_m,
        )
        if any(not isinstance(value, Fraction) or value <= 0 for value in positive) or any(
            not isinstance(value, Fraction) or value < 0 for value in nonnegative
        ):
            raise ValueError("Policy distances and tolerances must be exact valid Fractions.")
        if (
            isinstance(self.antipodal_tolerance_radians, bool)
            or not isfinite(self.antipodal_tolerance_radians)
            or not 0 < self.antipodal_tolerance_radians < pi
        ):
            raise ValueError("Invalid antipodal ambiguity tolerance.")


DEFAULT_ROUTE_POLICY = RoutePolicy()
