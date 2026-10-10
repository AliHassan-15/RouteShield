"""Immutable normalized route values; no transport or provider JSON structures."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from fractions import Fraction
from math import isfinite

from domain.route_policy import RoutePolicy

type RouteNumber = Fraction | Decimal | int | float


class RouteError(ValueError):
    """Safe machine-readable domain failures for later API mapping."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def exact_number(value: RouteNumber, field: str) -> Fraction:
    """Preserve exact Decimal/Fraction inputs and canonical float decimal text."""
    if isinstance(value, bool) or not isinstance(value, (Fraction, Decimal, int, float)):
        raise RouteError("INVALID_NUMBER", f"{field} must be a finite number, not a boolean.")
    if isinstance(value, Decimal) and not value.is_finite():
        raise RouteError("INVALID_NUMBER", f"{field} must be finite.")
    if isinstance(value, float):
        if not isfinite(value):
            raise RouteError("INVALID_NUMBER", f"{field} must be finite.")
        return Fraction(str(value))
    return Fraction(value)


@dataclass(frozen=True, slots=True)
class Coordinate:
    """Canonical WGS84 longitude/latitude; sequence order is traveled order."""

    longitude: float
    latitude: float

    def __post_init__(self) -> None:
        """Reject invalid coordinates without guessing swapped axes."""
        lon = exact_number(self.longitude, "longitude")
        lat = exact_number(self.latitude, "latitude")
        if not -180 <= lon <= 180 or not -90 <= lat <= 90:
            raise RouteError("INVALID_COORDINATE", "Coordinates must be valid WGS84 lon/lat.")
        object.__setattr__(self, "longitude", float(lon))
        object.__setattr__(self, "latitude", float(lat))


@dataclass(frozen=True, slots=True)
class TimingAnchor:
    """Geometry point index plus provider cumulative meters and elapsed seconds."""

    point_index: int
    distance_m: Fraction
    elapsed_s: Fraction


class TimingSource(StrEnum):
    ALIGNED = "ALIGNED_VERTEX_TIMING"
    PROGRESS = "SPARSE_PROGRESS_TIMING"
    GUIDANCE = "GUIDANCE_TIMING"


@dataclass(frozen=True, slots=True)
class TimingWarning:
    """Explicit fallback or endpoint reconciliation, never guessed uniform timing."""

    code: str
    source: TimingSource
    rejected_code: str | None = None


@dataclass(frozen=True, slots=True)
class Route:
    """Validated build_route output; collapsed geometry retains full timing evidence.

    Cumulative per-vertex arrays are aligned to collapsed geometry. Full anchors
    also retain repeated-distance waits, which one per-vertex array cannot encode.
    Provider chainage drives distance/time; geometric chainage drives interpolation.
    """

    geometry: tuple[Coordinate, ...]
    distance_m: Fraction
    duration_s: Fraction
    geometric_distances_m: tuple[Fraction, ...]
    cumulative_distances_m: tuple[Fraction, ...]
    cumulative_times_s: tuple[Fraction, ...]
    timing_anchors: tuple[TimingAnchor, ...]
    timing_source: TimingSource
    timing_warnings: tuple[TimingWarning, ...]
    policy: RoutePolicy

    @property
    def distance_miles(self) -> Fraction:
        """Convert with the exact policy scale, without display rounding."""
        return self.distance_m / self.policy.meters_per_mile


@dataclass(frozen=True, slots=True)
class Ownership:
    start_miles: Fraction
    end_miles: Fraction

    @property
    def owned_miles(self) -> Fraction:
        """Exact length of the midpoint interval."""
        return self.end_miles - self.start_miles


@dataclass(frozen=True, slots=True)
class Checkpoint:
    coordinate: Coordinate
    distance_m: Fraction
    elapsed_s: Fraction
    eta_utc: datetime
    ownership: Ownership

    @property
    def owned_miles(self) -> Fraction:
        """Expose exact midpoint mileage for aggregation."""
        return self.ownership.owned_miles


@dataclass(frozen=True, slots=True)
class IntervalWarning:
    code: str
    old_interval_miles: int
    new_interval_miles: int


@dataclass(frozen=True, slots=True)
class IntervalPlan:
    interval_miles: int
    checkpoint_count: int
    warnings: tuple[IntervalWarning, ...]


@dataclass(frozen=True, slots=True)
class RouteCheckpoints:
    route: Route
    checkpoints: tuple[Checkpoint, ...]


@dataclass(frozen=True, slots=True)
class TripCheckpoints:
    plan: IntervalPlan
    routes: tuple[RouteCheckpoints, ...]


@dataclass(frozen=True, slots=True)
class LocalCheckpoint:
    checkpoint: Checkpoint
    timezone_name: str
    local_time: datetime
    used_utc_fallback: bool
    warning_code: str | None
