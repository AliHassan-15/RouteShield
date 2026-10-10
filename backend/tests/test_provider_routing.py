"""ROUTE-01..10: synthetic sparse parsing, request semantics and bounded fallbacks."""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import cast

import httpx
import pytest
from domain.identity import stable_route_id
from domain.route_types import Coordinate, TimingSource
from providers.deadline import Deadline
from providers.errors import ErrorCode, ProviderError
from providers.tomtom import (
    TomTomRouter,
    fallback_waypoints,
    parse_route,
    parse_routes,
)
from providers.transport import HTTPResponse

from tests.provider_helpers import (
    DESTINATION,
    NOW,
    ORIGIN,
    SPARSE_POINTS,
    FakeClient,
    FakeTime,
    fixture,
    normalized_payload,
    response,
    route_payload,
    transport,
)


def test_three_routes_units_coordinate_order_and_sparse_anchors() -> None:
    routes = parse_routes(fixture("routing_three_routes.json"))
    assert len(routes) == 3
    for route, meters, seconds in zip(routes, (2983, 2893, 3083), (200, 220, 240), strict=True):
        assert route.distance_m == meters and route.duration_s == seconds
        assert route.geometry[0] == ORIGIN and route.geometry[-1] == DESTINATION
        assert len(route.geometry) == 3 and len(route.timing_anchors) == 2
        assert route.timing_source is TimingSource.PROGRESS
        assert len(route.cumulative_times_s) == len(route.geometry)


@pytest.mark.parametrize(
    "mutation",
    [
        "out_of_range",
        "non_monotonic",
        "wrong_start",
        "wrong_end",
        "wrong_distance",
        "wrong_time",
        "missing_progress",
        "missing_index",
        "boolean_index",
        "negative_distance",
        "nan_time",
        "missing_summary",
        "missing_geometry",
        "bad_coordinate",
        "zero_duration",
        "string_number",
    ],
)
def test_malformed_sparse_route_never_invents_timing(mutation: str) -> None:
    payload = route_payload(SPARSE_POINTS)
    anchors = cast(list[dict[str, object]], payload["progress"])
    summary = cast(dict[str, object], payload["summary"])
    if mutation == "out_of_range":
        anchors[1]["pointIndex"] = 100
    if mutation == "non_monotonic":
        anchors[1]["travelTimeInSeconds"] = 1000
    if mutation == "wrong_start":
        anchors[0]["distanceInMeters"] = 1
    if mutation == "wrong_end":
        anchors[-1]["pointIndex"] = 3
    if mutation == "wrong_distance":
        anchors[-1]["distanceInMeters"] = 0
    if mutation == "wrong_time":
        anchors[-1]["travelTimeInSeconds"] = 599 - 10
    if mutation == "missing_progress":
        del payload["progress"]
    if mutation == "missing_index":
        del anchors[1]["pointIndex"]
    if mutation == "boolean_index":
        anchors[1]["pointIndex"] = True
    if mutation == "negative_distance":
        anchors[1]["distanceInMeters"] = -1
    if mutation == "nan_time":
        anchors[1]["travelTimeInSeconds"] = float("nan")
    if mutation == "missing_summary":
        del payload["summary"]
    if mutation == "missing_geometry":
        payload["legs"] = []
    if mutation == "bad_coordinate":
        payload["legs"] = [{"points": [{"latitude": 91, "longitude": 0}]}]
    if mutation == "zero_duration":
        summary["travelTimeInSeconds"] = 0
    if mutation == "string_number":
        summary["lengthInMeters"] = "3000"
    with pytest.raises(ProviderError) as caught:
        parse_route(payload)
    assert caught.value.code is ErrorCode.MALFORMED_PROVIDER_RESPONSE


def guidance_payload() -> dict[str, object]:
    payload = route_payload(SPARSE_POINTS)
    progress = cast(list[dict[str, object]], payload["progress"])
    instructions = []
    for item in progress:
        point = SPARSE_POINTS[cast(int, item["pointIndex"])]
        instructions.append(
            {
                "pointIndex": item["pointIndex"],
                "point": {"latitude": point.latitude, "longitude": point.longitude},
                "routeOffsetInMeters": item["distanceInMeters"],
                "travelTimeInSeconds": item["travelTimeInSeconds"],
            }
        )
    payload["guidance"] = {"instructions": instructions}
    payload["progress"] = [{"pointIndex": "invalid"}]
    return payload


def test_valid_guidance_only_when_returned_and_mappable() -> None:
    route = parse_route(guidance_payload())
    assert route.timing_source is TimingSource.GUIDANCE
    assert route.timing_warnings[0].code == "GUIDANCE_TIMING_FALLBACK"
    assert route.cumulative_times_s[2] == 150  # Actual anchor, not distance-fraction timing.


@pytest.mark.parametrize("mutation", ["missing_endpoint", "unmappable_point", "missing_fields"])
def test_guidance_invalid_does_not_repair_bad_progress(mutation: str) -> None:
    payload = guidance_payload()
    instructions = cast(
        list[dict[str, object]], cast(dict[str, object], payload["guidance"])["instructions"]
    )
    if mutation == "missing_endpoint":
        instructions.pop()
    if mutation == "unmappable_point":
        instructions[1]["point"] = {"latitude": 35, "longitude": -100}
    if mutation == "missing_fields":
        del instructions[0]["routeOffsetInMeters"]
    with pytest.raises(ProviderError):
        parse_route(payload)


def test_endpoint_totals_tolerated_only_by_existing_policy() -> None:
    payload = route_payload(SPARSE_POINTS)
    progress = cast(list[dict[str, object]], payload["progress"])
    progress[-1]["travelTimeInSeconds"] = 600.5
    route = parse_route(payload)
    assert route.timing_anchors[-1].elapsed_s == 600
    assert route.timing_warnings[-1].code == "TIMING_ENDPOINT_RECONCILED"
    progress[-1]["travelTimeInSeconds"] = 602
    with pytest.raises(ProviderError):
        parse_route(payload)


def test_empty_and_missing_routes_have_distinct_errors() -> None:
    cases: tuple[tuple[dict[str, object], ErrorCode], ...] = (
        ({"routes": []}, ErrorCode.NO_ROUTE),
        ({}, ErrorCode.MALFORMED_PROVIDER_RESPONSE),
    )
    for payload, code in cases:
        with pytest.raises(ProviderError) as caught:
            parse_routes(payload)
        assert caught.value.code is code


def test_request_uses_exact_parameters_and_normalized_utc() -> None:
    clock = FakeTime()
    client = FakeClient([response(fixture("routing_three_routes.json"))])
    adapter = transport(client, clock)
    departure = NOW.astimezone(timezone(timedelta(hours=-4)))
    try:
        result = TomTomRouter(adapter, clock.utc).route_alternatives(
            ORIGIN, DESTINATION, departure, deadline=clock.deadline()
        )
        assert len(result.routes) == 3 and len(client.calls) == 1
        url, params, _ = client.calls[0]
        assert "/34.0,-100.0:34.02,-99.98/json" in url
        assert tuple(p for p in params if p[0] != "key") == (
            ("travelMode", "truck"),
            ("maxAlternatives", "2"),
            ("alternativeType", "anyRoute"),
            ("routeRepresentation", "polyline"),
            ("extendedRouteRepresentation", "distance"),
            ("extendedRouteRepresentation", "travelTime"),
            ("traffic", "false"),
            ("departAt", "2026-10-10T12:00:00Z"),
        )
        assert not any(
            "weight" in name.lower() or "axle" in name.lower() or "dimension" in name.lower()
            for name, _ in params
        )
        assert result.submitted_departure == NOW and result.routing_departure == NOW
        assert result.profile == "truck" and result.live_traffic is False
        assert result.attribution.confirmed is False
    finally:
        adapter.close()


def test_past_provider_rejection_changes_request_only() -> None:
    rejected = response(
        {"detailedError": {"code": "BAD_REQUEST", "message": "departAt is in the past"}}, 400
    )
    clock = FakeTime()
    client = FakeClient([rejected, response(fixture("routing_three_routes.json"))])
    adapter = transport(client, clock)
    submitted = NOW - timedelta(seconds=60)
    try:
        result = TomTomRouter(adapter, clock.utc).route_alternatives(
            ORIGIN, DESTINATION, submitted, deadline=clock.deadline()
        )
        assert len(client.calls) == 2
        assert dict(client.calls[0][1])["departAt"] == "2026-10-10T11:59:00Z"
        assert dict(client.calls[1][1])["departAt"] == "2026-10-10T12:00:00Z"
        assert result.submitted_departure == submitted and result.routing_departure == NOW
        assert result.warnings[0].code == "ROUTING_DEPARTURE_ADJUSTED"
    finally:
        adapter.close()


@pytest.mark.parametrize(
    "departure,body,status",
    [
        (NOW, {"detailedError": {"message": "departAt in the past"}}, 400),
        (NOW - timedelta(seconds=60), {"error": {"message": "something else"}}, 400),
        (NOW - timedelta(seconds=60), {"error": {"message": "departAt in the past"}}, 401),
    ],
)
def test_no_blind_past_departure_recovery(departure: datetime, body: object, status: int) -> None:
    clock = FakeTime()
    client = FakeClient([response(body, status)])
    adapter = transport(client, clock)
    try:
        with pytest.raises(ProviderError):
            TomTomRouter(adapter, clock.utc).route_alternatives(
                ORIGIN, DESTINATION, departure, deadline=clock.deadline()
            )
        assert len(client.calls) == 1
    finally:
        adapter.close()


@pytest.mark.parametrize(
    "departure", [NOW - timedelta(minutes=6), NOW + timedelta(days=8), NOW.replace(tzinfo=None)]
)
def test_invalid_departure_does_not_call_provider(departure: datetime) -> None:
    clock = FakeTime()
    client = FakeClient([])
    adapter = transport(client, clock)
    try:
        with pytest.raises(ProviderError):
            TomTomRouter(adapter, clock.utc).route_alternatives(
                ORIGIN, DESTINATION, departure, deadline=clock.deadline()
            )
        assert client.calls == []
    finally:
        adapter.close()


class WaypointClient(FakeClient):
    def __init__(
        self, durations: tuple[int, ...] = (600, 800, 850), *, mismatch: bool = False
    ) -> None:
        super().__init__([])
        self.durations = durations
        self.mismatch = mismatch

    def get(
        self,
        url: str,
        *,
        params: Sequence[tuple[str, str]],
        timeout: httpx.Timeout,
        deadline: Deadline,
    ) -> HTTPResponse:
        self.calls.append((url, tuple(params), timeout))
        locations = url.split("calculateRoute/", 1)[1].split("/json")[0]
        points = tuple(
            Coordinate(float(lon), float(lat))
            for lat, lon in (p.split(",") for p in locations.split(":"))
        )
        if self.mismatch and len(points) == 3:
            points = (Coordinate(-105, 34), *points[1:])
        return response(normalized_payload(points, self.durations[len(self.calls) - 1]))


def test_two_real_waypoint_calls_yield_distinct_routes() -> None:
    clock = FakeTime()
    client = WaypointClient()
    adapter = transport(client, clock)
    try:
        result = TomTomRouter(adapter, clock.utc).route_alternatives(
            ORIGIN, DESTINATION, NOW, deadline=clock.deadline()
        )
        assert len(client.calls) == 3 and len(result.routes) == 3
        assert result.warnings == ()
        assert all(r.duration_s <= 900 for r in result.routes)
        assert all(dict(params)["travelMode"] == "truck" for _, params, _ in client.calls)
    finally:
        adapter.close()


@pytest.mark.parametrize("durations,expected", [((600, 900, 901), 2), ((600, 901, 902), 1)])
def test_fallback_duration_cap_is_inclusive(durations: tuple[int, ...], expected: int) -> None:
    clock = FakeTime()
    client = WaypointClient(durations)
    adapter = transport(client, clock)
    try:
        result = TomTomRouter(adapter, clock.utc).route_alternatives(
            ORIGIN, DESTINATION, NOW, deadline=clock.deadline()
        )
        assert len(result.routes) == expected and len(client.calls) == 3
        assert (
            result.warnings[-1].code == "PARTIAL_ROUTES"
            and result.warnings[-1].route_count == expected
        )
    finally:
        adapter.close()


def test_fallback_matching_failure_is_discarded() -> None:
    clock = FakeTime()
    client = WaypointClient(mismatch=True)
    adapter = transport(client, clock)
    try:
        result = TomTomRouter(adapter, clock.utc).route_alternatives(
            ORIGIN, DESTINATION, NOW, deadline=clock.deadline()
        )
        assert len(result.routes) == 1 and len(client.calls) == 3
    finally:
        adapter.close()


def test_detour_cap_retains_fastest_discarded_native_duration() -> None:
    paths = (
        (ORIGIN, Coordinate(-99.99, 34.01), DESTINATION),
        (ORIGIN, Coordinate(-99.99, 34.0101), DESTINATION),
    )
    ordered = sorted(paths, key=lambda p: stable_route_id(parse_route(route_payload(p))))
    # Canonical order retains the 800s near-clone and discards the 600s path.
    primary = {"routes": [route_payload(ordered[0], 800), route_payload(ordered[1], 600)]}

    class NativeThenWaypointClient(WaypointClient):
        def get(
            self,
            url: str,
            *,
            params: Sequence[tuple[str, str]],
            timeout: httpx.Timeout,
            deadline: Deadline,
        ) -> HTTPResponse:
            if not self.calls:
                self.calls.append((url, tuple(params), timeout))
                return response(primary)
            return super().get(url, params=params, timeout=timeout, deadline=deadline)

    clock, client = FakeTime(), NativeThenWaypointClient((600, 1000, 1000))
    adapter = transport(client, clock)
    try:
        result = TomTomRouter(adapter, clock.utc).route_alternatives(
            ORIGIN, DESTINATION, NOW, deadline=clock.deadline()
        )
        assert len(result.routes) == 1 and result.routes[0].duration_s == 800
        assert len(client.calls) == 3  # 1000s >1.5*600; would fit incorrect 1.5*800.
        assert result.warnings[-1].route_count == 1
    finally:
        adapter.close()


@pytest.mark.parametrize(
    "extra",
    [
        response({"routes": []}),
        response({"detailedError": {"code": "NO_ROUTE_FOUND"}}, 400),
        response({}),
        response(normalized_payload(SPARSE_POINTS)),
        httpx.ReadTimeout("synthetic"),
    ],
)
def test_failed_or_duplicate_fallbacks_do_not_fabricate_routes(
    extra: HTTPResponse | Exception,
) -> None:
    clock = FakeTime()
    client = FakeClient([response(normalized_payload(SPARSE_POINTS)), extra, extra])
    adapter = transport(client, clock)
    try:
        result = TomTomRouter(adapter, clock.utc).route_alternatives(
            ORIGIN, DESTINATION, NOW, deadline=clock.deadline()
        )
        assert len(result.routes) == 1 and len(client.calls) == 3
        assert result.warnings[-1].code == "PARTIAL_ROUTES"
    finally:
        adapter.close()


@pytest.mark.parametrize("status", [401, 429])
def test_auth_quota_fallback_failures_stop(status: int) -> None:
    clock = FakeTime()
    client = FakeClient([response(normalized_payload(SPARSE_POINTS)), response({}, status)])
    adapter = transport(client, clock)
    try:
        with pytest.raises(ProviderError):
            TomTomRouter(adapter, clock.utc).route_alternatives(
                ORIGIN, DESTINATION, NOW, deadline=clock.deadline()
            )
        assert len(client.calls) == 2
    finally:
        adapter.close()


def test_short_deadline_skips_fallback_and_warns() -> None:
    clock = FakeTime()
    client = FakeClient([response(normalized_payload(SPARSE_POINTS))])
    adapter = transport(client, clock)
    try:
        result = TomTomRouter(adapter, clock.utc).route_alternatives(
            ORIGIN, DESTINATION, NOW, deadline=clock.deadline(2)
        )
        assert len(client.calls) == 1 and len(result.routes) == 1
        assert [w.code for w in result.warnings] == ["FALLBACK_SKIPPED_DEADLINE", "PARTIAL_ROUTES"]
    finally:
        adapter.close()


def test_waypoint_construction_is_deterministic_and_one_per_side() -> None:
    route = parse_route(route_payload((Coordinate(0, 0), Coordinate(1, 0))))
    points = fallback_waypoints(route)
    assert points == fallback_waypoints(route)
    assert points[0].latitude > 0 > points[1].latitude
    assert points[0].longitude == pytest.approx(0.5) and points[1].longitude == pytest.approx(0.5)
    offset = route.distance_m * Fraction(1, 20)
    assert abs(points[0].latitude) == pytest.approx(
        float(offset / route.policy.earth_radius_m) * 180 / 3.141592653589793
    )


def test_repeated_route_requests_not_cached() -> None:
    clock = FakeTime()
    payload = response(fixture("routing_three_routes.json"))
    client = FakeClient([payload, payload])
    adapter = transport(client, clock)
    router = TomTomRouter(adapter, clock.utc)
    try:
        first = router.route_alternatives(ORIGIN, DESTINATION, NOW, deadline=clock.deadline())
        second = router.route_alternatives(ORIGIN, DESTINATION, NOW, deadline=clock.deadline())
        assert first == second and len(client.calls) == 2
        assert not any(name.endswith("cache") for name in vars(router))
    finally:
        adapter.close()
