"""API/ROUTE/WX/RANK acceptance integration with labeled synthetic adapters only."""

from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
from itertools import permutations
from typing import Any

import pytest
from domain.identity import stable_route_id
from providers.contracts import Unavailable, UnavailableReason, WeatherValues
from providers.forecast import utc_epoch

from tests.api_helpers import (
    NOW,
    Harness,
    hazards,
    ratio,
    request_body,
    routes,
)
from tests.api_helpers import api as api


def by_lat(data: dict[str, Any], latitude: float) -> dict[str, Any]:
    return next(r for r in data["routes"] if r["geometry"][0][1] == latitude)


def test_full_pipeline_hand_calculated(api: Harness) -> None:
    def field(point: Any, hour: int) -> WeatherValues:
        latitude = round(point.latitude, 2)
        if latitude == 0:
            return hazards(
                "0"
                if point.longitude == 0 or point.longitude > 0.30
                else "35"
                if point.longitude > 0.20
                else "45"
            )
        return hazards("25" if latitude == 0.02 else "35")

    api.weather.value = field
    status, data = api.post()
    assert status == 200
    first, winner, high = (by_lat(data, lat) for lat in (0, 0.02, 0.04))
    # Midpoint ownership [5,10,6.5,1.5]: Low6.5, Severe10, High6.5; numerator66.
    summary = first["summary"]
    assert ratio(summary["average_risk"]) == Fraction(66, 23)
    assert ratio(summary["miles_by_level"]["SEVERE"]) == 10
    assert ratio(summary["miles_by_level"]["HIGH"]) == Fraction(13, 2)
    assert ratio(summary["miles_by_level"]["LOW"]) == Fraction(13, 2)
    assert [r["route_id"] for r in data["routes"]] == [
        winner["route_id"],
        high["route_id"],
        first["route_id"],
    ]
    assert data["recommended_route_id"] == winner["route_id"]
    assert data["decisive_criterion"] == "HIGH_MILES"
    assert {fact["criterion"] for fact in data["comparison_facts"]} == {
        "HIGH_MILES",
        "SEVERE_MILES",
    }
    assert "23" in data["explanation"] and "High" in data["explanation"]
    assert data["warnings"] == []
    assert api.router.deadlines == api.weather.deadlines
    assert data["metadata"]["provider_calls"] == {"routing": 1, "geocoding": 0, "weather": 1}
    assert ratio(data["metadata"]["quota_units_reserved"]) == 12
    assert data["metadata"]["simulated"] is False
    assert api.weather.window is not None
    assert api.weather.window.end_epoch == int(utc_epoch(NOW)) + 49 * 3600


@pytest.mark.parametrize("boundary,wind,competitor", [(30000, "45", "snow"), (40000, "35", "rain")])
def test_load_changes_recommendation(
    api: Harness, boundary: int, wind: str, competitor: str
) -> None:
    api.weather.value = lambda p, t: (
        hazards(wind)
        if round(p.latitude, 2) == 0
        else (hazards(snow="2.5") if competitor == "snow" else hazards(rain=".3"))
        if round(p.latitude, 2) == 0.02
        else hazards("55")
    )
    before = api.post(request_body(load_weight_lb=boundary))[1]
    after = api.post(request_body(load_weight_lb=boundary + 1))[1]
    assert before["recommended_route_id"] == by_lat(before, 0)["route_id"]
    assert after["recommended_route_id"] == by_lat(after, 0.02)["route_id"]
    assert by_lat(after, 0)["checkpoints"][0]["risk"]["final_risk"] == (
        "NO_TRAVEL" if boundary == 30000 else "SEVERE"
    )
    assert by_lat(before, 0)["checkpoints"][0]["risk"]["final_risk"] == (
        "SEVERE" if boundary == 30000 else "HIGH"
    )


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("blocked", "ALL_BLOCKED"),
        ("incomplete", "ALL_INCOMPLETE"),
        ("mixed", "NO_FULLY_ASSESSED_TRAVELABLE_ROUTE"),
        ("one_assessed", "BEST_FULLY_ASSESSED_AVAILABLE"),
        ("known_block", "ALL_BLOCKED"),
        ("partial_batch", "RECOMMENDED"),
    ],
)
def test_status_variants(api: Harness, mode: str, expected: str) -> None:
    missing = Unavailable(UnavailableReason.PROVIDER_FAILURE)
    blocked_missing = Unavailable(
        UnavailableReason.MISSING_FIELD, ("rain",), WeatherValues(Decimal("55"), None, Decimal(0))
    )
    api.weather.value = lambda p, t: (
        hazards("55")
        if mode == "blocked"
        else missing
        if mode == "incomplete"
        else blocked_missing
        if mode == "known_block"
        else (hazards("55") if round(p.latitude, 2) != 0.04 else missing)
        if mode == "mixed"
        else (hazards() if round(p.latitude, 2) == 0 else missing)
        if mode == "one_assessed"
        else (missing if round(p.latitude, 2) == 0.04 else hazards())
    )
    status, data = api.post()
    assert status == 200 and data["recommendation_status"] == expected
    for route in data["routes"]:
        if ratio(route["summary"]["unknown_miles"]):
            assert route["summary"]["average_risk"] is None and route["rank"] is None
    if mode == "known_block":
        assert all(r["travel_status"] == "BLOCKED" for r in data["routes"])
        assert all(
            cp["risk"]["final_risk"] == "UNKNOWN" and cp["risk"]["known_blocked"]
            for r in data["routes"]
            for cp in r["checkpoints"]
        )
        assert data["least_blocked_route_id"] is None
    if mode in ("blocked", "known_block"):
        assert "BLOCKED_TRIP" in {w["code"] for w in data["warnings"]}
        assert data["recommended_route_id"] is None


def test_quota_exhaustion_is_incomplete_200(api: Harness) -> None:
    reservation = api.service.ledger.reserve(Fraction(200))
    assert reservation is not None
    api.service.ledger.daily_limit = 200
    status, data = api.post()
    assert status == 200 and data["recommendation_status"] == "ALL_INCOMPLETE"
    assert {r["travel_status"] for r in data["routes"]} == {"INCOMPLETE"}
    assert "DEMO_QUOTA_REACHED" in {w["code"] for w in data["warnings"]}
    assert data["metadata"]["provider_calls"]["weather"] == 0


def test_out_of_horizon_and_timezone_fallback(api: Harness) -> None:
    api.weather.horizon_end = int(utc_epoch(NOW))
    api.weather.fallback = True
    status, data = api.post()
    assert status == 200
    assert "FORECAST_HORIZON_LIMIT" in {w["code"] for w in data["warnings"]}
    assert "UTC_FALLBACK" in {w["code"] for w in data["warnings"]}
    for route in data["routes"]:
        for cp in route["checkpoints"]:
            assert cp["timezone"] is None and cp["local_time"] is None and cp["utc_fallback"]
            assert cp["risk"]["final_risk"] == "UNKNOWN"


@pytest.mark.parametrize("count", [1, 2])
def test_partial_routes(api: Harness, count: int) -> None:
    api.router.routes = api.router.routes[:count]
    data = api.post()[1]
    assert data["route_count"] == count
    assert "PARTIAL_ROUTES" in {w["code"] for w in data["warnings"]}


def test_interval_budget_bump(api: Harness) -> None:
    api.router.routes = routes(1260)
    data = api.post(request_body(checkpoint_interval_miles=10))[1]
    assert data["trip"]["effective_interval_miles"] == 25
    assert "INTERVAL_INCREASED" in {w["code"] for w in data["warnings"]}
    assert ratio(data["metadata"]["quota_units_reserved"]) <= 200


def test_trip_too_large(api: Harness) -> None:
    api.router.routes = routes(10001)
    status, data = api.post(request_body(checkpoint_interval_miles=50))
    assert status == 422 and data["error"]["code"] == "TRIP_TOO_LARGE"
    assert api.weather.calls == 0


def test_pooling_not_conservative_precount(api: Harness) -> None:
    # Distinct canonical IDs within100m: 3*71 raw samples ->71 mandatory unique.
    base = routes(700)[0]
    api.router.routes = tuple(
        replace(base, geometry=tuple(replace(p, latitude=i * 0.0001) for p in base.geometry))
        for i in range(3)
    )
    data = api.post(request_body(checkpoint_interval_miles=10))[1]
    assert data["trip"]["effective_interval_miles"] == 10
    assert ratio(data["metadata"]["quota_units_reserved"]) == 71


@pytest.mark.parametrize("order", list(permutations(range(3))))
def test_route_order_independence(api: Harness, order: tuple[int, ...]) -> None:
    original = api.router.routes
    baseline = api.post()[1]
    api.router.routes = tuple(original[i] for i in order)
    reordered = api.post()[1]
    assert reordered["recommended_route_id"] == baseline["recommended_route_id"]
    assert [r["route_id"] for r in reordered["routes"]] == [
        r["route_id"] for r in baseline["routes"]
    ]
    assert reordered["comparison_facts"] == baseline["comparison_facts"]
    assert set(r["route_id"] for r in reordered["routes"]) == {stable_route_id(r) for r in original}


def test_window_extends_through_latest_eta(api: Harness) -> None:
    api.router.routes = tuple(
        replace(
            r,
            duration_s=Fraction(60 * 3600),
            cumulative_times_s=(Fraction(0), Fraction(60 * 3600)),
            timing_anchors=tuple(
                replace(a, elapsed_s=Fraction(60 * 3600) if a.point_index else Fraction(0))
                for a in r.timing_anchors
            ),
        )
        for r in api.router.routes
    )
    status, _ = api.post()
    assert status == 200
    assert api.weather.window is not None
    assert api.weather.window.end_epoch == int(utc_epoch(NOW)) + 61 * 3600


def test_exact_decimal_load_from_json(api: Harness) -> None:
    api.weather.value = lambda p, t: hazards("45")
    raw = (
        __import__("json")
        .dumps(request_body())
        .replace('"load_weight_lb": 0', '"load_weight_lb": 30000.0000000000000000001')
    )
    data = api.post(raw=raw)[1]
    assert data["trip"]["load_weight_lb"] == "30000.0000000000000000001"
    assert all(r["travel_status"] == "BLOCKED" for r in data["routes"])


def test_swappable_weather_protocol(api: Harness) -> None:
    # FakeWeather has no HTTP client, Django import or Open-Meteo payload parser.
    api.weather.value = lambda p, t: hazards("25", ".25", "1")
    result = api.service.analyze(request_body(), api.service.begin())
    assert result["recommendation_status"] == "RECOMMENDED"


@pytest.mark.parametrize("miles,expected", [(100, 10), (101, 25), (500, 25), (501, 50)])
def test_adaptive_default_from_longest(api: Harness, miles: int, expected: int) -> None:
    api.router.routes = (routes()[0], *routes(miles)[1:])
    assert api.post()[1]["trip"]["effective_interval_miles"] == expected


def test_no_routes_is_typed_422(api: Harness) -> None:
    api.router.routes = ()
    status, data = api.post()
    assert status == 422 and data["error"]["code"] == "NO_ROUTE"
    assert api.weather.calls == 0


def test_weather_failure_uses_unknown_200(api: Harness) -> None:
    def fail() -> None:
        raise RuntimeError("https://secret.invalid?key=unsafe")

    api.weather.effect = fail
    status, data = api.post()
    assert status == 200 and data["recommendation_status"] == "ALL_INCOMPLETE"
    assert all(
        cp["risk"]["final_risk"] == "UNKNOWN" for r in data["routes"] for cp in r["checkpoints"]
    )


def test_cache_diagnostics_keep_exact_age(api: Harness) -> None:
    # The programmable fake supplies a cache-hit series; no route/geocode cache exists.
    api.weather.cached = True
    data = api.post()[1]
    assert data["metadata"]["weather_cache"]["misses"] == 0
    assert ratio(data["metadata"]["weather_cache"]["ages_seconds"][0]) == Fraction(1, 3)
    assert data["metadata"]["provider_calls"]["weather"] == 0
    assert ratio(data["metadata"]["quota_units_reserved"]) == 0


def test_malformed_weather_shape_retains_routes(
    api: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = api.weather.fetch

    def malformed(*args: Any, **kwargs: Any) -> Any:
        return replace(original(*args, **kwargs), series=())

    monkeypatch.setattr(api.weather, "fetch", malformed)
    status, data = api.post()
    assert status == 200 and data["recommendation_status"] == "ALL_INCOMPLETE"
    assert "WEATHER_UNAVAILABLE" in {w["code"] for w in data["warnings"]}


def test_single_route_raw_count_over_200_can_pool(api: Harness) -> None:
    from domain.geometry import build_route

    from tests.route_helpers import straight_route

    base, tail = straight_route(55), straight_route(5)
    points = tuple(base.geometry[i % 2] for i in range(201)) + (tail.geometry[-1],)
    positions = tuple(Fraction(55 * i) for i in range(201)) + (Fraction(11005),)
    route = build_route(
        points,
        positions[-1] * base.policy.meters_per_mile,
        603,
        cumulative_distances_m=tuple(p * base.policy.meters_per_mile for p in positions),
        cumulative_times_s=tuple(i * 3 for i in range(len(points))),
    )
    api.router.routes = (route,)
    status, data = api.post(request_body(checkpoint_interval_miles=50))
    assert status == 200
    assert len(data["routes"][0]["checkpoints"]) > 200
    assert ratio(data["metadata"]["quota_units_reserved"]) <= 200
