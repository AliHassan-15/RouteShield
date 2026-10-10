"""Compact columnar mapping, shared forecasts and bounded trip envelope; synthetic only."""

import gzip
import json
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from random import Random
from typing import Any, cast

import pytest
from apps.routing.heatmap import classify_cell, compressed_size, fit_payload
from domain.checkpoints import generate_checkpoints
from domain.corridor import corridor_samples, truck_position
from domain.route_policy import DEFAULT_MAX_ROUTE_DISTANCE_MILES
from providers.contracts import HourlyWeather, Unavailable, UnavailableReason, WeatherValues
from providers.forecast import utc_epoch
from providers.pooling import pool_coordinates

from tests.api_helpers import NOW, Harness, hazards, ratio, request_body, routes
from tests.api_helpers import api as api
from tests.route_helpers import straight_route
from tests.weather_helpers import payload
from tests.weather_helpers import series as normalized_series


def test_corridor_skips_checkpoints_and_follows_geometry() -> None:
    route = straight_route(73)
    checkpoints = generate_checkpoints(route, NOW, 25)
    samples = corridor_samples(route, checkpoints)
    assert [d / route.policy.meters_per_mile for d, _ in samples] == [10, 20, 30, 40, 60, 70]
    assert all(p.latitude == 0 for _, p in samples)


@pytest.mark.parametrize("elapsed,marker", [(0, 0), (3600, 10), (7200, 20), (7201, None)])
def test_truck_positions_use_anchors(elapsed: int, marker: int | None) -> None:
    route = straight_route(20, positions_miles=(0, 5, 20), times_s=(0, 1800, 7200))
    point = truck_position(route, Fraction(elapsed))
    assert (None if point is None else point[2]) == marker
    if point is not None:
        assert point[0] == 0


def test_truck_waits_are_stationary() -> None:
    from domain.geometry import build_route
    from domain.route_types import TimingAnchor

    base = straight_route(20, positions_miles=(0, 10, 20), times_s=(0, 3600, 10800))
    route = build_route(
        base.geometry,
        base.distance_m,
        10800,
        progress_anchors=(
            TimingAnchor(0, Fraction(0), Fraction(0)),
            TimingAnchor(1, base.distance_m / 2, Fraction(3600)),
            TimingAnchor(1, base.distance_m / 2, Fraction(7200)),
            TimingAnchor(2, base.distance_m, Fraction(10800)),
        ),
    )
    point = truck_position(route, Fraction(5400))
    assert point is not None and point[2] == 10


@pytest.mark.parametrize(
    "values,load,level,dominant,strength",
    [
        (("30", "0", "0"), 0, "2", "1", 50),
        (("0", ".375", "0"), 0, "3", "2", 50),
        (("0", "0", "2.5"), 0, "4", "3", 50),
        (("35", "0", "0"), 45000, "4", "4", 0),
        (("45", "0", "0"), 45000, "5", "4", 100),
        (("55", "0", "0"), 0, "5", "1", 100),
        (("25", ".1", ".5"), 0, "2", "1", 0),
        (("0", "1", "0"), 0, "4", "2", 100),
    ],
)
def test_cell_intensity_and_dominance(
    values: tuple[str, str, str], load: int, level: str, dominant: str, strength: int
) -> None:
    series = normalized_series(payload())
    sample = next(v for v in series.hours.values() if isinstance(v, HourlyWeather))
    cell = classify_cell(replace(sample, values=hazards(*values)), Decimal(load))
    assert (cell.level, cell.dominant, cell.intensity) == (level, dominant, strength)
    if dominant == "4":
        assert cell.hazards[0] == level


@pytest.mark.parametrize(
    "kind,expected,reason",
    [
        ("partial", "0", None),
        ("empty", "9", "MISSING_FIELD"),
        ("unavailable", "9", "OUT_OF_HORIZON"),
    ],
)
def test_missing_cells_are_not_calm(kind: str, expected: str, reason: str | None) -> None:
    series = normalized_series(payload())
    sample = next(v for v in series.hours.values() if isinstance(v, HourlyWeather))
    value = (
        Unavailable(UnavailableReason.OUT_OF_HORIZON)
        if kind == "unavailable"
        else replace(
            sample, values=WeatherValues(Decimal(55) if kind == "partial" else None, None, None)
        )
    )
    cell = classify_cell(value, Decimal(45000))
    assert cell.level == expected and cell.intensity == 0
    assert (None if cell.reason is None else cell.reason.value) == reason
    if kind == "partial":
        assert cell.hazards[0] == "5"  # Known wind block remains visible under UNKNOWN.
        assert cell.known_blocked and cell.known_risk_floor == "5"


def test_pool_one_pass_and_one_weather_fetch(api: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.routing import service

    api.router.routes = routes(73)
    original = pool_coordinates
    calls = []

    def pool(*args: Any, **kwargs: Any) -> Any:
        # Any stays at the test instrumentation boundary, not application data.
        calls.append((len(args[0]), len(args[1])))
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "pool_coordinates", pool)
    status, data = api.post(request_body(checkpoint_interval_miles=25))
    heatmap = data["heatmap"]
    assert status == 200 and calls == [(12, 18)] and api.weather.calls == 1
    assert ratio(data["metadata"]["quota_units_reserved"]) == heatmap["point_count"]
    assert heatmap["point_count"] > heatmap["density"]["mandatory_point_count"]


def test_overlapping_routes_share_all_pool_indices(api: Harness) -> None:
    base = routes(73)[0]
    api.router.routes = tuple(
        replace(base, geometry=tuple(replace(p, latitude=i * 0.0001) for p in base.geometry))
        for i in range(3)
    )
    heatmap = api.post(request_body(checkpoint_interval_miles=25))[1]["heatmap"]
    assert heatmap["point_count"] == 10
    mappings = heatmap["route_mappings"]
    assert len({tuple(m["checkpoint_point_indices"]) for m in mappings}) == 1
    assert (
        len({tuple(p["point_index"] for p in m["optional_point_mappings"]) for m in mappings}) == 1
    )


def test_checkpoint_and_heatmap_same_instant_load_and_encoding(api: Harness) -> None:
    api.weather.value = lambda p, t: hazards("45", "0", "0")
    data = api.post(
        request_body(departure_time=(NOW + timedelta(hours=1)).isoformat(), load_weight_lb=45000)
    )[1]
    heatmap = data["heatmap"]
    assert heatmap["frame_count"] == len(heatmap["frames"]) == 49
    first = heatmap["frames"][0]
    for route in data["routes"]:
        mapping = next(m for m in heatmap["route_mappings"] if m["route_id"] == route["route_id"])
        point = mapping["checkpoint_point_indices"][0]
        assert (
            heatmap["legends"]["levels"][first["levels"][point]]
            == route["checkpoints"][0]["risk"]["final_risk"]
        )
    for frame in heatmap["frames"]:
        assert (
            len(frame["levels"])
            == len(frame["dominant_hazards"])
            == len(frame["intensities"])
            == heatmap["point_count"]
        )
        assert set(frame["levels"]) == {"5"} and set(frame["dominant_hazards"]) == {"4"}
        assert set(frame["known_blocked"]) == {"1"} and set(frame["known_risk_floors"]) == {"5"}
    assert data["capabilities"]["hazard_filter"] is True


def test_minutes_and_dst_hours_are_absolute(api: Harness) -> None:
    # Fall-back transition: 01:30 EDT +1 absolute hour is 01:30 EST, not02:30 EST.
    departure = "2026-11-01T01:30:00-04:00"
    api.clock.utc = lambda: datetime.fromisoformat(departure) - timedelta(hours=3)  # type: ignore[method-assign]
    api.service.clock = api.clock.utc
    api.weather.value = lambda p, t: hazards("25" if t % 7200 else "35")
    data = api.post(request_body(departure_time=departure, departure_timezone="America/New_York"))[
        1
    ]
    heatmap = data["heatmap"]
    assert heatmap["reference_time"] == "2026-11-01T05:30:00Z"
    assert heatmap["frames"][1]["timestamp"] == "2026-11-01T06:30:00Z"
    assert heatmap["frames"][0]["levels"] != heatmap["frames"][1]["levels"]


def test_horizon_and_partial_warnings(api: Harness) -> None:
    api.weather.horizon_end = int(utc_epoch(NOW)) + 2 * 3600
    data = api.post()[1]
    heatmap = data["heatmap"]
    assert heatmap["forecast_coverage"]["last_usable_hour"] == 1
    assert set(heatmap["frames"][2]["levels"]) == {"9"}
    assert set(heatmap["frames"][2]["unavailable_reasons"].values()) == {"OUT_OF_HORIZON"}
    assert {"FORECAST_HORIZON_LIMIT", "HEATMAP_PARTIAL_AVAILABILITY"} <= set(heatmap["warnings"])


def test_synthetic_largest_supported_payload_200_points_49_frames(api: Harness) -> None:
    # Dense geometry at the default envelope:6001 vertices/route, adverse cell entropy.
    base = straight_route(
        DEFAULT_MAX_ROUTE_DISTANCE_MILES,
        positions_miles=tuple(
            Fraction(i * DEFAULT_MAX_ROUTE_DISTANCE_MILES, 6000) for i in range(6001)
        ),
        times_s=tuple(Fraction(i) for i in range(6001)),
    )
    api.router.routes = tuple(
        replace(base, geometry=tuple(replace(p, latitude=i * 0.02) for p in base.geometry))
        for i in range(3)
    )
    api.weather.value = lambda p, t: hazards(
        str(25 + (int(abs(p.longitude) * 1000) + t // 3600) % 35), ".3", "1.5"
    )
    data = api.post(request_body(checkpoint_interval_miles=10))[1]
    # Maximum pool-width columnar stress, independently varying cells for poor compression.
    noise = Random(0)  # Deterministic synthetic data only; production has no randomness.
    heatmap = data["heatmap"]
    for frame in heatmap["frames"]:
        for name in ("levels", "dominant_hazards"):
            frame[name] = "".join(str(noise.randint(1, 4)) for _ in range(200))
        frame["intensities"] = [noise.randint(0, 100) for _ in range(200)]
        frame["known_blocked"] = "0" * 200
        frame["known_risk_floors"] = frame["levels"]
        for name in frame["hazard_levels"]:
            frame["hazard_levels"][name] = "".join(str(noise.randint(1, 5)) for _ in range(200))
    heatmap["points"] = [
        [round(noise.uniform(-120, -115), 5), round(noise.uniform(30, 35), 5)] for _ in range(200)
    ]
    heatmap["forecast_coverage"]["last_usable_hour_by_point"] = [48] * 200
    heatmap["point_count"] = 200
    assert len(data["routes"]) == 3 and len(heatmap["frames"]) == 49
    measured = compressed_size(data)
    fit_payload(data)
    assert data["capabilities"]["hazard_filter"] == (measured < 300000)
    assert compressed_size(data) < 500000


def test_provisional_default_and_environment_override() -> None:
    from config.environment import number
    from django.conf import settings

    assert DEFAULT_MAX_ROUTE_DISTANCE_MILES == 300
    assert number({}, "MAX_ROUTE_DISTANCE_MILES", DEFAULT_MAX_ROUTE_DISTANCE_MILES) == 300
    assert (
        number(
            {"MAX_ROUTE_DISTANCE_MILES": "275"},
            "MAX_ROUTE_DISTANCE_MILES",
            DEFAULT_MAX_ROUTE_DISTANCE_MILES,
        )
        == 275
    )
    assert cast(float, settings.PROVIDER_CONFIG["max_route_distance_miles"]) > 0


def test_filters_omitted_and_size_failure_explicit(
    api: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.routing import heatmap
    from apps.routing.errors import APIError

    data = api.post()[1]
    monkeypatch.setattr(heatmap, "FILTER_BUDGET_BYTES", 1)
    fit_payload(data)
    assert data["heatmap"]["hazard_filters_included"] is False
    assert data["capabilities"]["hazard_filter"] is False
    assert all("hazard_levels" not in f for f in data["heatmap"]["frames"])
    monkeypatch.setattr(heatmap, "PAYLOAD_BUDGET_BYTES", 1)
    with pytest.raises(APIError) as caught:
        fit_payload(data)
    assert caught.value.code == "TRIP_TOO_LARGE"


@pytest.mark.parametrize(
    "delta,rejected", [(Fraction(-1, 1000), False), (Fraction(0), False), (Fraction(1, 1000), True)]
)
def test_precheck_boundary_no_provider(
    api: Harness, monkeypatch: pytest.MonkeyPatch, delta: Fraction, rejected: bool
) -> None:
    threshold = api.service.max_route_distance_miles * Fraction(4, 5)
    monkeypatch.setattr(
        "apps.routing.service.point_distance",
        lambda *args: float((threshold + delta) * routes()[0].policy.meters_per_mile),
    )
    status, data = api.post()
    assert status == (422 if rejected else 200)
    assert api.router.calls == (0 if rejected else 1)
    if rejected:
        assert api.weather.calls == 0 and data["error"]["details"] == {"max_distance_miles": 400}
        assert "longer than the supported distance for this demo" in data["error"]["message"]


@pytest.mark.parametrize(
    "distance,rejected",
    [(Fraction("399.999"), False), (Fraction(400), False), (Fraction("400.001"), True)],
)
def test_postcheck_shortest_boundary(api: Harness, distance: Fraction, rejected: bool) -> None:
    api.router.routes = (straight_route(distance),)
    status, data = api.post()
    assert status == (422 if rejected else 200)
    assert api.router.calls == 1 and api.weather.calls == (0 if rejected else 1)
    if rejected:
        assert data["error"]["details"]["max_distance_miles"] == 400


def test_longer_alternatives_kept_and_post_not_cached(api: Harness) -> None:
    api.router.routes = (straight_route(390), straight_route(430), straight_route(470))
    status, data = api.post()
    assert status == 200 and data["route_count"] == 3
    response = api.client.post(
        "/api/v1/route-analysis/",
        json.dumps(
            request_body(origin={"label": "Origin\u2028test", "latitude": 0, "longitude": 0})
        ),
        content_type="application/json",
        HTTP_ACCEPT="application/json; indent=4",
    )
    assert response.status_code == 200 and response["Cache-Control"] == "no-store"
    assert len(gzip.compress(response.content, compresslevel=9, mtime=0)) == compressed_size(
        response.json()
    )


def test_density_reduction_is_disclosed(api: Harness) -> None:
    api.router.routes = routes(400)
    api.service.max_coordinates = 60
    data = api.post(request_body(checkpoint_interval_miles=50))[1]
    heatmap = data["heatmap"]
    assert heatmap["point_count"] <= 60 and heatmap["density"]["reduced"]
    assert (
        heatmap["density"]["optional_selected_count"]
        < heatmap["density"]["optional_candidate_count"]
    )
    assert "HEATMAP_DENSITY_REDUCED" in heatmap["warnings"]
