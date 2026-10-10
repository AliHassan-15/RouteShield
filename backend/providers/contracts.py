"""Provider-neutral immutable values, located here by the user's scope decision.

Protocols exchange normalized coordinates/routes and these values, never raw
HTTP responses or TomTom shapes. This module has no transport/framework imports.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from fractions import Fraction
from typing import Protocol

from domain.route_types import Coordinate, Route

from providers.deadline import Deadline


@dataclass(frozen=True, slots=True)
class Attribution:
    provider: str = "TomTom"
    text: str = "TomTom attribution pending user confirmation of section 17.3."
    confirmed: bool = False
    source_url: str | None = None
    licence_url: str | None = None


PENDING_ATTRIBUTION = Attribution()


@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_id: str
    label: str
    coordinate: Coordinate
    region: str | None
    country: str | None
    match_type: str
    score: Fraction


@dataclass(frozen=True, slots=True)
class GeocodeResult:
    candidates: tuple[Candidate, ...]
    attribution: Attribution


@dataclass(frozen=True, slots=True)
class ProviderWarning:
    code: str
    route_count: int | None = None


@dataclass(frozen=True, slots=True)
class RoutingResult:
    routes: tuple[Route, ...]
    warnings: tuple[ProviderWarning, ...]
    attribution: Attribution
    submitted_departure: datetime
    routing_departure: datetime
    profile: str = "truck"
    live_traffic: bool = False


class GeocodingProvider(Protocol):
    def geocode(self, query: str, *, deadline: Deadline) -> GeocodeResult:
        """Return candidates in provider order; never choose the first implicitly."""
        ...


class RoutingProvider(Protocol):
    def route_alternatives(
        self,
        origin: Coordinate,
        destination: Coordinate,
        departure: datetime,
        *,
        deadline: Deadline,
    ) -> RoutingResult:
        """Return up to three genuine distinct normalized routes and warnings."""
        ...


class UnavailableReason(StrEnum):
    OUT_OF_HORIZON = "OUT_OF_HORIZON"
    MISSING_HOUR = "MISSING_HOUR"
    MISSING_FIELD = "MISSING_FIELD"
    PAST_TIME = "PAST_TIME"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    DEMO_QUOTA_REACHED = "DEMO_QUOTA_REACHED"


@dataclass(frozen=True, slots=True)
class WeatherWindow:
    start_epoch: int
    end_epoch: int

    @property
    def hours(self) -> tuple[int, ...]:
        """Requested whole UTC hours, including both boundary rows."""
        return tuple(range(self.start_epoch, self.end_epoch + 1, 3600))


@dataclass(frozen=True, slots=True)
class WeatherValues:
    wind_mph: Decimal | None = None
    rain_in_hr: Decimal | None = None
    snow_in_hr: Decimal | None = None
    gust_mph: Decimal | None = None


@dataclass(frozen=True, slots=True)
class WeatherSource:
    components: Mapping[str, Fraction | None] = field(repr=False)
    units: Mapping[str, str | None] = field(repr=False)
    hourly_average_rates: bool = True


@dataclass(frozen=True, slots=True)
class WeatherProvenance:
    provider: str
    model: str
    fetched_at: Fraction  # UTC epoch seconds; requested selection, not guessed actual model.
    cache_hit: bool = False


@dataclass(frozen=True, slots=True)
class HourlyWeather:
    forecast_epoch: int
    values: WeatherValues
    source: WeatherSource
    provenance: WeatherProvenance


@dataclass(frozen=True, slots=True)
class Unavailable:
    reason: UnavailableReason
    missing_fields: tuple[str, ...] = ()
    # D08: incomplete is never a complete safe sample, but known block evidence
    # must survive for the later domain checkpoint classifier.
    known_values: WeatherValues = field(default_factory=WeatherValues)
    source: WeatherSource | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class WeatherSeries:
    coordinate: Coordinate
    window: WeatherWindow
    hours: Mapping[int, HourlyWeather | Unavailable]
    provenance: WeatherProvenance
    timezone: str
    utc_offset_seconds: int
    timezone_fallback: bool = False

    @property
    def complete(self) -> bool:
        return tuple(self.hours) == self.window.hours and all(
            isinstance(value, HourlyWeather) for value in self.hours.values()
        )


@dataclass(frozen=True, slots=True)
class ForecastLookup:
    eta_epoch: Fraction
    forecast_epoch: int
    result: HourlyWeather | Unavailable


@dataclass(frozen=True, slots=True)
class WeatherDiagnostics:
    cache_hits: int
    cache_misses: int
    ages_seconds: tuple[Fraction, ...]
    upstream_attempts: int


@dataclass(frozen=True, slots=True)
class WeatherResult:
    series: tuple[WeatherSeries, ...]
    failed_indices: tuple[int, ...]
    attribution: Attribution
    diagnostics: WeatherDiagnostics


class WeatherProvider(Protocol):
    def fetch(
        self, coordinates: Sequence[Coordinate], window: WeatherWindow, *, deadline: Deadline
    ) -> WeatherResult:
        """Return reusable normalized hourly series in the input coordinate order."""
        ...


@dataclass(frozen=True, slots=True, order=True)
class PointKey:
    route_id: str
    index: int
    mandatory: bool


@dataclass(frozen=True, slots=True)
class PoolPoint:
    key: PointKey
    coordinate: Coordinate
    distance_m: Fraction | None = None


@dataclass(frozen=True, slots=True)
class PointAssignment:
    pooled_index: int
    distance_m: float
    coarsened: bool = False


@dataclass(frozen=True, slots=True)
class PoolingResult:
    coordinates: tuple[Coordinate, ...]
    mandatory_count: int
    assignments: Mapping[PointKey, PointAssignment]
    optional_input_count: int
    optional_selected_count: int
    optional_stride: int
    actual_spacing_m: Mapping[str, float]
    warnings: tuple[str, ...]
