"""Provider-neutral immutable values, located here by the user's scope decision.

Protocols exchange normalized coordinates/routes and these values, never raw
HTTP responses or TomTom shapes. This module has no transport/framework imports.
"""

from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from typing import Protocol

from domain.route_types import Coordinate, Route

from providers.deadline import Deadline


@dataclass(frozen=True, slots=True)
class Attribution:
    provider: str = "TomTom"
    text: str = "TomTom attribution pending user confirmation of section 17.3."
    confirmed: bool = False


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
