"""TomTom truck routing and forward geocoding, normalized behind clean protocols."""

import re
import unicodedata
from bisect import bisect_right
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from hashlib import sha256
from math import asin, atan2, cos, degrees, radians, sin
from typing import cast
from urllib.parse import quote

from domain.geometry import build_route, interpolate_coordinate
from domain.route_policy import DEFAULT_ROUTE_POLICY
from domain.route_types import Coordinate, Route, RouteError, TimingAnchor, exact_number

from providers.contracts import (
    PENDING_ATTRIBUTION,
    Attribution,
    Candidate,
    GeocodeResult,
    ProviderWarning,
    RoutingResult,
)
from providers.deadline import Deadline
from providers.distinctness import PolylineIndex, distinct_routes, point_distance
from providers.errors import ErrorCode, ProviderError
from providers.transport import TomTomTransport, json_object


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ProviderError(ErrorCode.MALFORMED_PROVIDER_RESPONSE)
    return cast(dict[str, object], value)


def _array(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ProviderError(ErrorCode.MALFORMED_PROVIDER_RESPONSE)
    return cast(list[object], value)


def _number(value: object) -> Fraction:
    failed = False
    result = Fraction(0)
    try:
        result = exact_number(cast(int, value), "provider value")
        if result < 0:
            failed = True
    except (RouteError, TypeError, ValueError, OverflowError):
        failed = True
    if failed:
        raise ProviderError(ErrorCode.MALFORMED_PROVIDER_RESPONSE) from None
    return result


def _point(value: object, *, geocode: bool = False) -> Coordinate:
    obj = _object(value)
    failed = False
    result: Coordinate | None = None
    try:
        result = Coordinate(
            cast(float, obj.get("lon" if geocode else "longitude")),
            cast(float, obj.get("lat" if geocode else "latitude")),
        )
    except (RouteError, TypeError, ValueError, OverflowError):
        failed = True
    if failed or result is None:
        raise ProviderError(ErrorCode.MALFORMED_PROVIDER_RESPONSE) from None
    return result


def sanitize_query(query: str) -> str:
    """Remove controls, preserve word separation, then enforce label and lookup limits."""
    if not isinstance(query, str):
        raise ProviderError(ErrorCode.INVALID_REQUEST)
    cleaned = "".join(
        " " if c.isspace() else c
        for c in query
        if c.isspace() or not unicodedata.category(c).startswith("C")
    )
    cleaned = " ".join(cleaned.split())
    if not 2 <= len(cleaned) <= 200 or len(cleaned) < 3:
        raise ProviderError(ErrorCode.INVALID_REQUEST)
    return cleaned


def _text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProviderError(ErrorCode.MALFORMED_PROVIDER_RESPONSE)
    return (
        " ".join("".join(c for c in value if not unicodedata.category(c).startswith("C")).split())
        or None
    )


def parse_candidates(payload: dict[str, object], limit: int = 5) -> tuple[Candidate, ...]:
    """Stable normalized IDs; preserve response order and score ties, never first-match."""
    candidates = []
    for item in _array(payload.get("results"))[:limit]:
        result = _object(item)
        address = _object(result.get("address"))
        coordinate = _point(result.get("position"), geocode=True)
        country = _text(address.get("country")) or _text(address.get("countryCode"))
        region = _text(address.get("countrySubdivisionName")) or _text(
            address.get("countrySubdivision")
        )
        label = _text(address.get("freeformAddress")) or ", ".join(
            v for v in (_text(address.get("municipality")), region, country) if v
        )
        match_type = _text(result.get("type"))
        if not label or not match_type:
            raise ProviderError(ErrorCode.MALFORMED_PROVIDER_RESPONSE)
        score = _number(result.get("score"))
        identity = "|".join(
            (
                label,
                str(coordinate.longitude),
                str(coordinate.latitude),
                region or "",
                country or "",
                match_type,
            )
        )
        candidate_id = "candidate_" + sha256(identity.encode("utf-8")).hexdigest()
        candidates.append(
            Candidate(candidate_id, label, coordinate, region, country, match_type, score)
        )
    return tuple(candidates)


def _anchors(
    value: object, *, guidance: bool = False, geometry: Sequence[Coordinate] = ()
) -> tuple[TimingAnchor, ...]:
    anchors = []
    for item in _array(value):
        obj = _object(item)
        index = obj.get("pointIndex")
        if type(index) is not int:
            raise ProviderError(ErrorCode.MALFORMED_PROVIDER_RESPONSE)
        if guidance:
            # A guidance index can precede an interior segment point. The existing
            # domain model supports vertex anchors only: reject unmappable offsets.
            point = _point(obj.get("point"))
            if not 0 <= index < len(geometry) or point_distance(
                point, geometry[index], float(DEFAULT_ROUTE_POLICY.earth_radius_m)
            ) > float(DEFAULT_ROUTE_POLICY.distance_endpoint_tolerance_m):
                raise ProviderError(ErrorCode.MALFORMED_PROVIDER_RESPONSE)
        anchors.append(
            TimingAnchor(
                index,
                _number(obj.get("routeOffsetInMeters" if guidance else "distanceInMeters")),
                _number(obj.get("travelTimeInSeconds")),
            )
        )
    return tuple(anchors)


def parse_route(value: object) -> Route:
    """Parse observed fields, relying on existing strict sparse-anchor validation."""
    obj = _object(value)
    summary = _object(obj.get("summary"))
    distance, duration = (
        _number(summary.get("lengthInMeters")),
        _number(summary.get("travelTimeInSeconds")),
    )
    if distance <= 0 or duration <= 0:
        raise ProviderError(ErrorCode.MALFORMED_PROVIDER_RESPONSE)
    geometry = tuple(
        _point(p) for leg in _array(obj.get("legs")) for p in _array(_object(leg).get("points"))
    )
    progress: tuple[TimingAnchor, ...] = ()
    guidance: tuple[TimingAnchor, ...] = ()
    try:
        progress = _anchors(obj.get("progress"))
    except ProviderError:
        pass
    if "guidance" in obj:
        try:
            guidance = _anchors(
                _object(obj["guidance"]).get("instructions"), guidance=True, geometry=geometry
            )
        except ProviderError:
            pass
    failed = False
    route: Route | None = None
    try:
        route = build_route(
            geometry, distance, duration, progress_anchors=progress, guidance_anchors=guidance
        )
    except (RouteError, ValueError, TypeError, ZeroDivisionError):
        failed = True
    if failed or route is None:
        raise ProviderError(ErrorCode.MALFORMED_PROVIDER_RESPONSE) from None
    return route


def parse_routes(payload: dict[str, object]) -> tuple[Route, ...]:
    """Malformed routes fail the primary payload; empty routes mean NO_ROUTE."""
    values = _array(payload.get("routes"))
    if not values:
        raise ProviderError(ErrorCode.NO_ROUTE)
    if len(values) > 3:
        raise ProviderError(ErrorCode.MALFORMED_PROVIDER_RESPONSE)
    return tuple(parse_route(value) for value in values)


@dataclass(frozen=True, slots=True)
class RoutingPolicy:
    max_fallback_calls: int = 2
    duration_factor: Fraction = Fraction(3, 2)
    side_offset_fraction: Fraction = Fraction(1, 20)
    minimum_offset_m: float = 1000
    maximum_offset_m: float = 50000
    endpoint_tolerance_m: float = 1000
    minimum_fallback_seconds: float = 3

    def __post_init__(self) -> None:
        if type(self.max_fallback_calls) is not int or not 0 <= self.max_fallback_calls <= 2:
            raise ProviderError(ErrorCode.INVALID_REQUEST)


ROUTING_POLICY = RoutingPolicy()


def fallback_waypoints(
    route: Route, policy: RoutingPolicy = ROUTING_POLICY
) -> tuple[Coordinate, Coordinate]:
    """Offset the chainage midpoint left/right of its segment bearing by clamped 5%."""
    midpoint = interpolate_coordinate(route, route.distance_m / 2)
    i = min(
        bisect_right(route.cumulative_distances_m, route.distance_m / 2) - 1,
        len(route.geometry) - 2,
    )
    a, b = route.geometry[i : i + 2]
    lat1, lat2 = radians(a.latitude), radians(b.latitude)
    delta = radians(b.longitude - a.longitude)
    bearing = atan2(
        sin(delta) * cos(lat2), cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(delta)
    )
    offset = min(
        policy.maximum_offset_m,
        max(policy.minimum_offset_m, float(route.distance_m * policy.side_offset_fraction)),
    )
    angular = offset / float(route.policy.earth_radius_m)
    lat, lon = radians(midpoint.latitude), radians(midpoint.longitude)
    points = []
    for side in (-1, 1):
        direction = bearing + side * radians(90)
        target_lat = asin(sin(lat) * cos(angular) + cos(lat) * sin(angular) * cos(direction))
        target_lon = lon + atan2(
            sin(direction) * sin(angular) * cos(lat), cos(angular) - sin(lat) * sin(target_lat)
        )
        points.append(Coordinate((degrees(target_lon) + 180) % 360 - 180, degrees(target_lat)))
    return points[0], points[1]


class TomTomGeocoder:
    def __init__(
        self,
        transport: TomTomTransport,
        *,
        countries: tuple[str, ...] = (),
        attribution: Attribution = PENDING_ATTRIBUTION,
    ) -> None:
        if any(not re.fullmatch(r"[A-Z]{2,3}", c) for c in countries):
            raise ProviderError(ErrorCode.INVALID_REQUEST)
        self._transport, self._countries, self._attribution = transport, countries, attribution

    def geocode(self, query: str, *, deadline: Deadline) -> GeocodeResult:
        """Unrestricted by default; optional ISO countrySet, no deprecated typeahead."""
        query = sanitize_query(query)
        params = [("limit", "5"), ("storeResult", "false")]
        if self._countries:
            params.append(("countrySet", ",".join(self._countries)))
        response = self._transport.get(
            "/search/2/geocode/" + quote(query, safe="") + ".json",
            params,
            routing=False,
            deadline=deadline,
        )
        result = GeocodeResult(parse_candidates(json_object(response)), self._attribution)
        deadline.check()
        return result


class TomTomRouter:
    def __init__(
        self,
        transport: TomTomTransport,
        clock: Callable[[], datetime],
        *,
        policy: RoutingPolicy = ROUTING_POLICY,
        attribution: Attribution = PENDING_ATTRIBUTION,
        allow_past_recovery: bool = True,
    ) -> None:
        self._transport, self._clock = transport, clock
        self._policy, self._attribution, self._past_recovery = (
            policy,
            attribution,
            allow_past_recovery,
        )

    def _request(
        self, points: Sequence[Coordinate], departure: datetime, deadline: Deadline
    ) -> tuple[Route, ...]:
        path = (
            "/routing/1/calculateRoute/"
            + ":".join(f"{p.latitude},{p.longitude}" for p in points)
            + "/json"
        )
        params = (
            ("travelMode", "truck"),
            ("maxAlternatives", "2"),
            ("alternativeType", "anyRoute"),
            ("routeRepresentation", "polyline"),
            ("extendedRouteRepresentation", "distance"),
            ("extendedRouteRepresentation", "travelTime"),
            ("traffic", "false"),
            ("departAt", departure.isoformat().replace("+00:00", "Z")),
        )
        response = self._transport.get(path, params, routing=True, deadline=deadline)
        return parse_routes(json_object(response))

    def _matches(
        self,
        route: Route,
        origin: Coordinate,
        destination: Coordinate,
        waypoint: Coordinate | None = None,
    ) -> bool:
        radius = float(route.policy.earth_radius_m)
        return (
            point_distance(route.geometry[0], origin, radius) <= self._policy.endpoint_tolerance_m
            and point_distance(route.geometry[-1], destination, radius)
            <= self._policy.endpoint_tolerance_m
            and (waypoint is None or PolylineIndex(route).matches(waypoint))
        )

    def route_alternatives(
        self,
        origin: Coordinate,
        destination: Coordinate,
        departure: datetime,
        *,
        deadline: Deadline,
    ) -> RoutingResult:
        """Single alternatives request plus at most two actual bounded waypoint calls."""
        if (
            not isinstance(origin, Coordinate)
            or not isinstance(destination, Coordinate)
            or origin == destination
            or not isinstance(departure, datetime)
            or departure.tzinfo is None
            or departure.utcoffset() is None
        ):
            raise ProviderError(ErrorCode.INVALID_REQUEST)
        submitted = departure.astimezone(UTC)
        now = self._clock().astimezone(UTC)
        if not now - timedelta(minutes=5) <= submitted <= now + timedelta(days=7):
            raise ProviderError(ErrorCode.INVALID_REQUEST)
        requested = submitted
        warnings: list[ProviderWarning] = []
        rejected: ProviderError | None = None
        candidates: tuple[Route, ...] = ()
        try:
            candidates = self._request((origin, destination), requested, deadline)
        except ProviderError as error:
            rejected = ProviderError(
                error.code, past_departure_rejected=error.past_departure_rejected
            )
        if rejected is not None:
            if (
                self._past_recovery
                and rejected.past_departure_rejected
                and now - timedelta(minutes=5) <= submitted < now
            ):
                requested = self._clock().astimezone(UTC)
                candidates = self._request((origin, destination), requested, deadline)
                warnings.append(ProviderWarning("ROUTING_DEPARTURE_ADJUSTED"))
            else:
                raise rejected from None
        if any(not self._matches(r, origin, destination) for r in candidates):
            raise ProviderError(ErrorCode.MALFORMED_PROVIDER_RESPONSE)
        accepted = distinct_routes(candidates)
        deadline.check()
        if len(accepted) < 3 and self._policy.max_fallback_calls:
            main = min(accepted, key=lambda r: (r.duration_s, r.distance_m))
            # Canonical duplicate filtering can discard the fastest native path;
            # it must not increase the permitted detour duration.
            limit = min(r.duration_s for r in candidates) * self._policy.duration_factor
            for waypoint in fallback_waypoints(main, self._policy)[
                : self._policy.max_fallback_calls
            ]:
                if len(accepted) == 3:
                    break
                if deadline.remaining() <= self._policy.minimum_fallback_seconds:
                    warnings.append(ProviderWarning("FALLBACK_SKIPPED_DEADLINE"))
                    break
                try:
                    extra = self._request((origin, waypoint, destination), requested, deadline)
                except ProviderError as error:
                    if error.code in {ErrorCode.PROVIDER_AUTH, ErrorCode.QUOTA_EXCEEDED}:
                        raise
                    deadline.check()
                    warnings.append(ProviderWarning("FALLBACK_UNAVAILABLE"))
                    continue
                eligible = tuple(
                    r
                    for r in extra
                    if r.duration_s <= limit and self._matches(r, origin, destination, waypoint)
                )
                accepted = distinct_routes((*accepted, *eligible))
                deadline.check()
        if not accepted:
            raise ProviderError(ErrorCode.NO_ROUTE)
        if len(accepted) < 3:
            warnings.append(ProviderWarning("PARTIAL_ROUTES", len(accepted)))
        deadline.check()
        return RoutingResult(accepted, tuple(warnings), self._attribution, submitted, requested)
