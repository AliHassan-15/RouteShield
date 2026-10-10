"""Independent offline hand calculations and audit regressions; synthetic providers only."""

import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from fractions import Fraction
from typing import Any

import httpx
import pytest
from django.core.cache import cache
from django.test import override_settings
from domain.route_types import Coordinate
from providers.contracts import Unavailable, UnavailableReason, WeatherValues
from providers.deadline import Deadline
from providers.errors import ErrorCode, ProviderError
from providers.quota import QuotaLedger, Reservation, quota_units
from providers.tomtom import TomTomRouter
from providers.transport import HTTPResponse
from providers.weather_transport import SendCounter

from tests.api_helpers import ANALYSIS, Harness, hazards, ratio, request_body, routes, schema_check
from tests.api_helpers import NOW as API_NOW
from tests.api_helpers import api as api
from tests.provider_helpers import (
    DESTINATION,
    NOW,
    ORIGIN,
    SPARSE_POINTS,
    FakeClient,
    FakeTime,
    response,
    route_payload,
    transport,
)
from tests.route_helpers import straight_route
from tests.weather_helpers import VARIABLES, WINDOW, CoordinateClient, adapter, points


@pytest.mark.parametrize(
    "delays,reads,expired",
    [
        ((25, 6, 3.9), (25, 10, 4), False),
        ((25, 7), (25, 10), False),
        ((25, 6, 4), (25, 10, 4), True),
    ],
)
def test_routing_read_allowance_is_not_a_reset_stage_deadline(
    delays: tuple[float, ...], reads: tuple[float, ...], expired: bool
) -> None:
    clock = FakeTime()

    class ClockClient(FakeClient):
        def get(
            self,
            url: str,
            *,
            params: Sequence[tuple[str, str]],
            timeout: httpx.Timeout,
            deadline: Deadline,
        ) -> HTTPResponse:
            assert deadline.remaining() > 0
            clock.seconds += delays[len(self.calls)]
            return super().get(url, params=params, timeout=timeout, deadline=deadline)

    client = ClockClient([response({"routes": [route_payload(SPARSE_POINTS)]})] * len(delays))
    adapter = transport(client, clock)
    deadline = clock.deadline()
    try:
        router = TomTomRouter(adapter, clock.utc)
        if expired:
            with pytest.raises(ProviderError) as caught:
                router.route_alternatives(ORIGIN, DESTINATION, NOW, deadline=deadline)
            assert caught.value.code is ErrorCode.PROVIDER_TIMEOUT
        else:
            result = router.route_alternatives(ORIGIN, DESTINATION, NOW, deadline=deadline)
            assert len(result.routes) == 1  # Identical fallback responses never fabricate options.
            if len(delays) == 2:
                assert "FALLBACK_SKIPPED_DEADLINE" in {w.code for w in result.warnings}
        assert tuple(call[2].read for call in client.calls) == reads
        assert deadline.metrics()[0]["routing"] == len(delays)
        assert clock.seconds == pytest.approx(sum(delays)) and clock.seconds <= 35
    finally:
        adapter.close()


@pytest.mark.parametrize(
    "count,batches", [(108, (50, 50, 8)), (150, (50, 50, 50)), (200, (50,) * 4)]
)
def test_quota_hand_calculation_allows_full_default_pool(
    count: int, batches: tuple[int, ...]
) -> None:
    # 3 inclusive UTC days, 4 variables, 1 model: C*max(1,4/10)*max(1,3/14)=C.
    assert quota_units(count, len(VARIABLES), WINDOW) == count
    clock, client = FakeTime(), CoordinateClient()
    weather = adapter(client, clock)
    deadline = clock.deadline()
    try:
        result = weather.fetch(points(count), WINDOW, deadline=deadline)
        sizes = sorted(len(dict(call)["latitude"].split(",")) for call in client.calls)
        assert sizes == sorted(batches)
        assert result.failed_indices == () and len(result.series) == count
        assert weather.transport.ledger.used == count
        assert deadline.metrics() == (
            {"routing": 0, "geocoding": 0, "weather": len(batches)},
            Fraction(count),
        )
        assert weather.transport.ledger.daily_limit == 8000
        assert weather.transport.ledger.request_limit == 200
    finally:
        weather.close()


def test_pipeline_weather_follows_nonuniform_checkpoint_eta(api: Harness) -> None:
    base = straight_route(40, positions_miles=(0, 10, 20, 40), times_s=(0, 1800, 7200, 10800))
    api.router.routes = tuple(
        replace(base, geometry=tuple(replace(p, latitude=i * 0.02) for p in base.geometry))
        for i in range(3)
    )
    start = int(API_NOW.timestamp())
    api.weather.value = lambda p, hour: hazards(
        {0: "0", 1: "25", 2: "35", 3: "45"}.get((hour - start) // 3600, "0")
    )
    status, data = api.post(request_body(departure_time=API_NOW.isoformat()))
    assert status == 200
    for route in data["routes"]:
        cps = route["checkpoints"]
        assert [ratio(c["elapsed_seconds"]) for c in cps] == [0, 1800, 7200, 9000, 10800]
        assert [c["weather"]["values"]["wind_mph"] for c in cps] == ["0", "25", "35", "45", "45"]
        assert [c["risk"]["final_risk"] for c in cps] == [
            "LOW",
            "MODERATE",
            "HIGH",
            "SEVERE",
            "SEVERE",
        ]
        assert ratio(route["summary"]["average_risk"]) == Fraction(115, 40)


def row_at(data: dict[str, Any], latitude: float) -> dict[str, Any]:
    """Any is confined to recursively schema-checked test-client JSON."""
    return next(r for r in data["routes"] if r["geometry"][0][1] == latitude)


def test_hand_scenario_a_high_miles_beat_mean_and_speed(api: Harness) -> None:
    api.router.routes = routes(100)
    end = api.router.routes[0].geometry[-1].longitude

    def field(point: Coordinate, hour: int) -> WeatherValues:
        mile = point.longitude * 100 / end
        if point.latitude == 0:
            return hazards(wind="45" if 5 < mile < 25 else "0")
        if round(point.latitude, 2) == 0.02:
            return hazards(rain=".30" if 5 < mile < 45 else "0")
        return hazards(snow=".5")

    api.weather.value = field
    status, data = api.post(request_body(load_weight_lb=0, checkpoint_interval_miles=10))
    assert status == 200
    first, second, third = (row_at(data, lat) for lat in (0, 0.02, 0.04))
    for route in data["routes"]:
        assert [ratio(c["owned_miles"]) for c in route["checkpoints"]] == [5] + [10] * 9 + [5]
        profile = route["risk_profile"]
        assert [ratio(s["start_mile"]) for s in profile] == [0] + list(range(5, 100, 10))
        assert [ratio(s["end_mile"]) for s in profile] == list(range(5, 100, 10)) + [100]
        assert [s["final_risk"] for s in profile] == [
            c["risk"]["final_risk"] for c in route["checkpoints"]
        ]
        assert [s["checkpoint_id"] for s in profile] == [c["id"] for c in route["checkpoints"]]
    for route, levels, totals, mean in (
        (
            first,
            ["LOW", "SEVERE", "SEVERE"] + ["LOW"] * 8,
            {"LOW": 80, "SEVERE": 20},
            Fraction(8, 5),
        ),
        (second, ["LOW"] + ["HIGH"] * 4 + ["LOW"] * 6, {"LOW": 60, "HIGH": 40}, Fraction(9, 5)),
        (third, ["MODERATE"] * 11, {"MODERATE": 100}, Fraction(2)),
    ):
        assert [c["risk"]["final_risk"] for c in route["checkpoints"]] == levels
        assert {
            k: ratio(v) for k, v in route["summary"]["miles_by_level"].items() if ratio(v)
        } == totals
        assert ratio(route["summary"]["average_risk"]) == mean
    assert data["recommended_route_id"] == third["route_id"]
    assert data["decisive_criterion"] == "HIGH_MILES"
    assert [r["route_id"] for r in data["routes"]] == [
        third["route_id"],
        second["route_id"],
        first["route_id"],
    ]
    assert ratio(first["duration_s"]) < ratio(second["duration_s"]) < ratio(third["duration_s"])


@pytest.mark.parametrize(
    "weight,levels,mean,no_travel,chosen",
    [
        (30000, ["HIGH", "SEVERE", "SEVERE", "NO_TRAVEL", "HIGH"], Fraction(4), 10, 0.02),
        (30001, ["HIGH", "NO_TRAVEL", "NO_TRAVEL", "NO_TRAVEL", "HIGH"], Fraction(9, 2), 30, 0.02),
        (40000, ["HIGH", "NO_TRAVEL", "NO_TRAVEL", "NO_TRAVEL", "HIGH"], Fraction(9, 2), 30, 0.02),
        (
            40001,
            ["SEVERE", "NO_TRAVEL", "NO_TRAVEL", "NO_TRAVEL", "SEVERE"],
            Fraction(19, 4),
            30,
            0.04,
        ),
    ],
)
def test_hand_scenario_b_strict_load_flips_and_recommendation(
    api: Harness, weight: int, levels: list[str], mean: Fraction, no_travel: int, chosen: float
) -> None:
    api.router.routes = routes(40)
    end = api.router.routes[0].geometry[-1].longitude

    def field(point: Coordinate, hour: int) -> WeatherValues:
        if point.latitude == 0:
            mile = point.longitude * 40 / end
            return hazards(wind=("44.9", "45", "54.9", "55", "44.9")[round(mile / 10)])
        return hazards(wind="44.9") if round(point.latitude, 2) == 0.02 else hazards(rain=".3")

    api.weather.value = field
    status, data = api.post(request_body(load_weight_lb=weight, checkpoint_interval_miles=10))
    first = row_at(data, 0)
    assert status == 200 and first["travel_status"] == "BLOCKED"
    assert [c["risk"]["final_risk"] for c in first["checkpoints"]] == levels
    assert [ratio(c["owned_miles"]) for c in first["checkpoints"]] == [5, 10, 10, 10, 5]
    assert ratio(first["summary"]["average_risk"]) == mean
    assert ratio(first["summary"]["no_travel_miles"]) == no_travel
    assert data["recommended_route_id"] == row_at(data, chosen)["route_id"]
    assert row_at(data, 0.02)["checkpoints"][0]["risk"]["final_risk"] == (
        "SEVERE" if weight > 40000 else "HIGH"
    )


def test_hand_scenario_c_unknown_known_block_survives_every_representation(
    api: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    api.router.routes = routes(23)
    end = api.router.routes[0].geometry[-1].longitude
    known = Unavailable(
        UnavailableReason.MISSING_FIELD, ("rain",), WeatherValues(Decimal(55), None, Decimal(0))
    )
    api.weather.value = lambda p, h: (
        known if p.latitude == 0 and 5 < p.longitude * 23 / end < 15 else hazards()
    )
    status, data = api.post(request_body(checkpoint_interval_miles=10))
    blocked = row_at(data, 0)
    assert status == 200 and blocked["travel_status"] == "BLOCKED"
    assert blocked["rank"] is None and blocked["group"] == "UNRANKED"
    assert data["recommended_route_id"] == row_at(data, 0.02)["route_id"]
    summary = blocked["summary"]
    assert ratio(summary["unknown_miles"]) == 10 and ratio(
        summary["coverage_fraction"]
    ) == Fraction(13, 23)
    assert summary["average_risk"] is None and summary["known_blocked"]
    assert ratio(summary["known_blocked_miles_diagnostic"]) == 10
    assert ratio(summary["no_travel_miles"]) == 0
    cp = blocked["checkpoints"][1]
    assert cp["risk"]["final_risk"] == "UNKNOWN" and cp["risk"]["known_risk_floor"] == "NO_TRAVEL"
    assert cp["risk"]["known_blocked"] and cp["risk"]["wind_risk"] == "NO_TRAVEL"
    profile = blocked["risk_profile"][1]
    assert (ratio(profile["start_mile"]), ratio(profile["end_mile"])) == (
        Fraction(5),
        Fraction(15),
    )
    assert profile["final_risk"] == "UNKNOWN" and profile["known_risk_floor"] == "NO_TRAVEL"
    assert profile["known_blocked"] and profile["checkpoint_id"] == cp["id"]
    heatmap = data["heatmap"]
    index = next(m for m in heatmap["route_mappings"] if m["route_id"] == blocked["route_id"])[
        "checkpoint_point_indices"
    ][1]
    frame = heatmap["frames"][0]
    assert frame["levels"][index] == "0"
    assert frame["known_blocked"][index] == "1" and frame["known_risk_floors"][index] == "5"
    assert frame["hazard_levels"]["wind"][index] == "5"
    from apps.routing.heatmap import fit_payload

    monkeypatch.setattr("apps.routing.heatmap.FILTER_BUDGET_BYTES", 1)
    fit_payload(data)
    assert "hazard_levels" not in frame
    assert frame["known_blocked"][index] == "1" and frame["known_risk_floors"][index] == "5"


@pytest.mark.parametrize("key", ["ROUTING_PROVIDER", "WEATHER_PROVIDER"])
def test_unsupported_provider_selector_cannot_be_silently_ignored(key: str) -> None:
    environment = dict(os.environ)
    environment[key] = "unsupported-synthetic-provider"
    result = subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert f"{key} must be" in result.stderr


def test_partial_heatmap_memo_keeps_availability_reasons_distinct(api: Harness) -> None:
    values = WeatherValues(Decimal(55), None, Decimal(0))
    start = int(API_NOW.timestamp())
    api.weather.value = lambda p, h: (
        Unavailable(UnavailableReason.MISSING_FIELD, ("rain",), values)
        if (h - start) // 3600 % 2
        else values
    )
    data = api.post()[1]
    heatmap = data["heatmap"]
    first, second = heatmap["frames"][:2]
    assert first["levels"] == second["levels"] == "0" * heatmap["point_count"]
    assert first["known_blocked"] == second["known_blocked"] == "1" * heatmap["point_count"]
    assert set(first["unavailable_reasons"].values()) == {"MISSING_FIELD"}
    assert second["unavailable_reasons"] == {}


@pytest.mark.parametrize("value", [[], {}])
def test_unhashable_scenario_returns_validation_error_not_internal_error(
    api: Harness, value: object
) -> None:
    status, data = api.post(request_body(simulation_scenario=value))
    assert status == 400 and data["error"]["code"] == "INVALID_SCENARIO"
    assert data["is_simulation"] is True and data["simulation_scenario"] is None
    assert api.router.calls == api.weather.calls == 0


@pytest.mark.parametrize("character", ["\x00", "\x7f", "\x85", "\u009f", "\ud800"])
def test_unicode_controls_and_surrogates_rejected_before_providers(
    api: Harness, character: str
) -> None:
    status, data = api.post(
        request_body(
            origin={"label": "Origin" + character + "label", "latitude": 0, "longitude": 0}
        )
    )
    assert status == 400 and data["error"]["details"] == {"origin.label": "CONTROL_CHARACTER"}
    assert api.router.calls == api.weather.calls == 0


def test_adversarial_client_matrix_returns_closed_safe_shapes(api: Harness) -> None:
    for raw in ("{", '{"x":NaN}', '{"x":Infinity}', '{"x":1,"x":2}', "[]", "null"):
        before = api.router.calls
        status, data = api.post(raw=raw)
        assert status == 400 and data["error"]["code"] == "VALIDATION_ERROR"
        assert api.router.calls == before
    for weight, expected in (
        (0, 200),
        (30000, 200),
        (30000.01, 200),
        (100000, 200),
        (100000.01, 400),
        ("NaN", 400),
        ("Infinity", 400),
        (True, 400),
        ([], 400),
    ):
        before = api.router.calls
        status, data = api.post(request_body(load_weight_lb=weight))
        assert status == expected
        if status == 400:
            assert data["error"]["code"] == "VALIDATION_ERROR" and api.router.calls == before
        else:
            assert Decimal(data["trip"]["load_weight_lb"]) == Decimal(str(weight))
    for departure in (API_NOW - timedelta(minutes=5), API_NOW + timedelta(days=7)):
        assert api.post(request_body(departure_time=departure.isoformat()))[0] == 200
    api.service.clock = lambda: API_NOW.replace(month=3, day=8)
    assert (
        api.post(
            request_body(
                departure_time="2026-03-08T02:30:00-05:00", departure_timezone="America/New_York"
            )
        )[0]
        == 400
    )
    api.service.clock = api.clock.utc
    for body in (
        request_body(unknown_field="ignored"),
        request_body(destination={"label": "Same place", "latitude": 0, "longitude": 0}),
    ):
        assert api.post(body)[0] == 400
    assert (
        api.post(request_body(origin={"label": "x" * 100000, "latitude": 0, "longitude": 0}))[0]
        == 413
    )
    assert api.post(content_type="text/plain")[0] == 415
    response = api.client.get(ANALYSIS)
    assert response.status_code == 405 and response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    schema_check("ErrorResponse", response.json())
    assert (
        api.post(
            request_body(
                origin={"label": "اسلام آباد / München 👩‍💻", "latitude": 0, "longitude": 0}
            )
        )[0]
        == 200
    )
    cache.clear()
    with override_settings(ANALYSIS_RATE_LIMIT=10, ANALYSIS_RATE_WINDOW_SECONDS=600):
        for _ in range(10):
            assert api.post()[0] == 200
        before = api.router.calls
        for _ in range(3):
            status, data = api.post()
            assert (
                status == 429
                and data["error"]["code"] == "THROTTLED"
                and api.router.calls == before
            )


def test_weather_cancelled_after_reservation_refunds_before_http() -> None:
    clock, client = FakeTime(), FakeClient([])
    deadline = clock.deadline()

    class CancelAfterReserve(QuotaLedger):
        def reserve(self, units: Fraction) -> Reservation | None:
            reservation = super().reserve(units)
            deadline.cancel()
            return reservation

    ledger = CancelAfterReserve(clock.utc)
    weather = adapter(client, clock, ledger=ledger)
    try:
        with pytest.raises(ProviderError):
            weather.transport._attempt([], WINDOW, 50, 4, deadline, SendCounter())
        assert ledger.used == 0 and client.calls == []
        assert deadline.metrics() == ({"routing": 0, "geocoding": 0, "weather": 0}, Fraction(50))
    finally:
        weather.close()
