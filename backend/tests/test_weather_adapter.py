"""WX/API/HEAT adapter boundary: reusable series, bounded batches, mapping and isolation."""

import threading
from collections.abc import Sequence
from decimal import Decimal
from fractions import Fraction
from typing import cast

import pytest
from domain.route_types import Coordinate, RouteError
from providers.contracts import (
    HourlyWeather,
    PointKey,
    PoolPoint,
    Unavailable,
    UnavailableReason,
    WeatherProvider,
    WeatherResult,
    WeatherWindow,
)
from providers.deadline import Deadline
from providers.limiter import ProviderLimiter
from providers.pooling import pool_coordinates
from providers.quota import QuotaLedger
from providers.transport import HTTPResponse
from providers.weather import OpenMeteoWeather
from providers.weather_transport import WeatherConfig

from tests.provider_helpers import FakeClient, FakeTime, response
from tests.weather_helpers import (
    POINT,
    START,
    WINDOW,
    CoordinateClient,
    adapter,
    hourly,
    payload,
    points,
)


@pytest.mark.parametrize(
    "count,batch_sizes",
    [(1, [1]), (50, [50]), (51, [1, 50]), (100, [50, 50]), (200, [50, 50, 50, 50])],
)
def test_request_shape_batch_sizes_and_coordinate_mapping(
    count: int, batch_sizes: list[int]
) -> None:
    time = FakeTime()
    client = CoordinateClient()
    service = adapter(client, time)
    coordinates = points(count)
    try:
        provider: WeatherProvider = service
        result = provider.fetch(coordinates, WINDOW, deadline=time.deadline())
        assert [s.coordinate for s in result.series] == list(coordinates)
        assert result.failed_indices == ()
        assert sorted(len(dict(p)["latitude"].split(",")) for p in client.calls) == batch_sizes
        assert result.diagnostics.upstream_attempts == len(batch_sizes)
        assert service.transport.ledger.used == count
        for index, weather in enumerate(result.series):
            row = weather.hours[START]
            assert isinstance(row, HourlyWeather)
            assert row.values.wind_mph == pytest.approx(Decimal(index) * Decimal("0.02"))
            assert row.values.rain_in_hr == Fraction(1, 4)
        for params in client.calls:
            values = dict(params)
            assert values["hourly"] == "wind_speed_10m,rain,showers,snowfall"
            assert values["wind_speed_unit"] == "mph" and values["precipitation_unit"] == "inch"
            assert values["timezone"] == "UTC" and values["timeformat"] == "unixtime"
            assert "models" not in values and "forecast_days" not in values
            assert values["start_hour"] == "2026-10-10T12:00"
            assert values["end_hour"] == "2026-10-12T12:00"
    finally:
        service.close()


def test_mapping_back_to_route_checkpoint_and_optional_never_swaps_values() -> None:
    mandatory = [PoolPoint(PointKey("b", i, True), p) for i, p in enumerate(points(60))]
    mandatory += [PoolPoint(PointKey("a", 0, True), POINT)]
    optional = [PoolPoint(PointKey("a", i, False), p) for i, p in enumerate(points(80))]
    pool = pool_coordinates(mandatory, optional)
    time = FakeTime()
    client = CoordinateClient()
    service = adapter(client, time, config=WeatherConfig(concurrency=1))
    try:
        result = service.fetch(pool.coordinates, WINDOW, deadline=time.deadline())
        for point in mandatory:
            assignment = pool.assignments[point.key]
            series = result.series[assignment.pooled_index]
            assert series.coordinate == point.coordinate
            row = series.hours[START]
            assert isinstance(row, HourlyWeather)
            assert row.values.wind_mph == Decimal(str(point.coordinate.longitude)) + 100
        sent = [float(x) for params in client.calls for x in dict(params)["longitude"].split(",")]
        assert sent == [p.longitude for p in pool.coordinates]
        assert pool.mandatory_count == 60 and len(pool.coordinates) == 80
    finally:
        service.close()


def test_two_concurrent_batches_bound_and_first_tier_scheduling() -> None:
    time = FakeTime()

    class BlockingClient(CoordinateClient):
        def __init__(self) -> None:
            super().__init__()
            self.active = self.peak = 0
            self.two_entered = threading.Event()
            self.release = threading.Event()
            self.first_batches: list[float] = []

        def get(
            self, url: str, *, params: Sequence[tuple[str, str]], timeout: object, deadline: object
        ) -> HTTPResponse:
            with self.lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
                self.first_batches.append(float(dict(params)["longitude"].split(",")[0]))
                if self.active == 2:
                    self.two_entered.set()
            self.release.wait(2)
            try:
                return super().get(url, params=params, timeout=timeout, deadline=deadline)
            finally:
                with self.lock:
                    self.active -= 1

    client = BlockingClient()
    service = adapter(client, time)
    outcome: list[WeatherResult] = []
    thread = threading.Thread(
        target=lambda: outcome.append(service.fetch(points(200), WINDOW, deadline=time.deadline()))
    )
    try:
        thread.start()
        assert client.two_entered.wait(1)
        assert sorted(client.first_batches) == [-100, -99]
        client.release.set()
        thread.join(3)
        assert not thread.is_alive() and client.peak == 2
        assert len(outcome[0].series) == 200 and outcome[0].failed_indices == ()
    finally:
        client.release.set()
        thread.join(3)
        service.close()


@pytest.mark.parametrize(
    "status,reason",
    [
        (400, UnavailableReason.PROVIDER_FAILURE),
        (429, UnavailableReason.QUOTA_EXCEEDED),
        (500, UnavailableReason.PROVIDER_FAILURE),
    ],
)
def test_failed_batch_only_its_own_coordinates(status: int, reason: UnavailableReason) -> None:
    time = FakeTime()
    client = FakeClient([response({}, status), response([payload(wind=20) for _ in range(50)])])
    service = adapter(client, time, config=WeatherConfig(concurrency=1))
    try:
        result = service.fetch(points(100), WINDOW, deadline=time.deadline())
        assert result.failed_indices == tuple(range(50))
        assert all(isinstance(s.hours[START], Unavailable) for s in result.series[:50])
        assert all(cast(Unavailable, s.hours[START]).reason is reason for s in result.series[:50])
        assert all(s.complete for s in result.series[50:])
        assert len(client.calls) == 2
        # Only successful complete coordinates enter the cache.
        second = service.fetch(points(50)[0:1] + points(100)[50:], WINDOW, deadline=time.deadline())
        assert second.diagnostics.cache_hits == 50 and second.diagnostics.cache_misses == 1
    finally:
        service.close()


def test_one_malformed_location_never_invalidates_neighbors() -> None:
    client = FakeClient([response([payload(wind=1), None, payload(wind=3)])])
    time = FakeTime()
    service = adapter(client, time)
    try:
        result = service.fetch(points(3), WINDOW, deadline=time.deadline())
        assert result.failed_indices == (1,)
        assert result.series[0].complete and result.series[2].complete
    finally:
        service.close()


@pytest.mark.parametrize("body", [{}, [], [payload()], None, {"hourly": None}, "malformed"])
def test_malformed_payload_never_becomes_complete(body: object) -> None:
    time = FakeTime()
    service = adapter(FakeClient([response(body)]), time)
    try:
        result = service.fetch(points(2), WINDOW, deadline=time.deadline())
        assert result.failed_indices == (0, 1)
        assert all(
            cast(Unavailable, s.hours[START]).reason is UnavailableReason.PROVIDER_FAILURE
            for s in result.series
        )
    finally:
        service.close()


def test_cache_hit_age_exact_expiry_and_no_extra_quota() -> None:
    time = FakeTime()
    client = FakeClient([response(payload()), response(payload())])
    service = adapter(client, time)
    try:
        first = service.fetch([POINT], WINDOW, deadline=time.deadline())
        assert first.diagnostics.cache_misses == 1 and first.diagnostics.cache_hits == 0
        time.seconds = 899
        second = service.fetch([POINT], WINDOW, deadline=time.deadline())
        assert second.diagnostics.cache_hits == 1 and second.diagnostics.upstream_attempts == 0
        assert second.diagnostics.ages_seconds == (Fraction(899),)
        assert len(client.calls) == 1 and service.transport.ledger.used == 1
        time.seconds = 900
        third = service.fetch([POINT], WINDOW, deadline=time.deadline())
        assert third.diagnostics.cache_misses == 1 and third.diagnostics.ages_seconds == (
            Fraction(0),
        )
        assert len(client.calls) == 2 and service.transport.ledger.used == 2
    finally:
        service.close()


def test_partial_not_cached_but_known_no_travel_wind_survives() -> None:
    time = FakeTime()
    doc = payload(wind=55)
    del hourly(doc)["showers"]
    client = FakeClient([response(doc), response(doc)])
    service = adapter(client, time)
    try:
        for _ in range(2):
            result = service.fetch([POINT], WINDOW, deadline=time.deadline())
            row = result.series[0].hours[START]
            assert isinstance(row, Unavailable) and row.known_values.wind_mph == 55
            assert row.known_values.rain_in_hr is None
            assert result.diagnostics.cache_hits == 0
        assert len(client.calls) == 2
    finally:
        service.close()


def test_quota_denial_is_explicit_with_zero_attempts() -> None:
    time = FakeTime()
    ledger = QuotaLedger(time.utc, daily_limit=49)
    client = FakeClient([])
    service = adapter(client, time, ledger=ledger)
    try:
        result = service.fetch(points(50), WINDOW, deadline=time.deadline())
        assert result.failed_indices == tuple(range(50))
        assert result.diagnostics.upstream_attempts == 0 and ledger.used == 0
        assert all(
            cast(Unavailable, s.hours[START]).reason is UnavailableReason.DEMO_QUOTA_REACHED
            for s in result.series
        )
    finally:
        service.close()


def test_expired_deadline_returns_unavailable_without_call_or_charge() -> None:
    time = FakeTime()
    client = FakeClient([])
    service = adapter(client, time)
    deadline = time.deadline()
    deadline.cancel()
    try:
        result = service.fetch([POINT], WINDOW, deadline=deadline)
        assert result.failed_indices == (0,) and not client.calls
        assert service.transport.ledger.used == 0
    finally:
        service.close()


def test_expired_deadline_cannot_return_cached_success() -> None:
    time = FakeTime()
    client = FakeClient([response(payload())])
    service = adapter(client, time)
    try:
        assert service.fetch([POINT], WINDOW, deadline=time.deadline()).series[0].complete
        deadline = time.deadline()
        deadline.cancel()
        result = service.fetch([POINT], WINDOW, deadline=deadline)
        assert result.failed_indices == (0,) and len(client.calls) == 1
        assert result.diagnostics.cache_hits == 0
    finally:
        service.close()


def test_window_beyond_documented_maximum_is_unavailable_without_http() -> None:
    time = FakeTime()
    client = FakeClient([])
    service = adapter(client, time)
    window = WeatherWindow(START + 20 * 86400, START + 22 * 86400)
    try:
        result = service.fetch([POINT], window, deadline=time.deadline())
        assert (
            cast(Unavailable, result.series[0].hours[window.start_epoch]).reason
            is UnavailableReason.OUT_OF_HORIZON
        )
        assert not client.calls and service.transport.ledger.used == 0
    finally:
        service.close()


def test_fake_provider_structurally_satisfies_shared_contract() -> None:
    class FakeWeather:
        def fetch(
            self, coordinates: Sequence[Coordinate], window: WeatherWindow, *, deadline: Deadline
        ) -> WeatherResult:
            time = FakeTime()
            service = adapter(CoordinateClient(window), time)
            try:
                return service.fetch(coordinates, window, deadline=deadline)
            finally:
                service.close()

    provider: WeatherProvider = FakeWeather()
    result = provider.fetch([POINT], WINDOW, deadline=FakeTime().deadline())
    assert result.series[0].complete


def test_weather_settings_composition_and_attribution_do_not_resolve_eligibility() -> None:
    from django.conf import settings

    time = FakeTime()
    values = dict(settings.PROVIDER_CONFIG)
    assert values["max_coordinates"] == 200 and values["weather_model"] == "best_match"
    values.update(
        weather_base_url="https://example.invalid/forecast",
        weather_model="gfs_seamless",
        weather_gusts=True,
        weather_daily_quota_units=500,
        weather_request_unit_limit=100,
        weather_cache_ttl_seconds=10,
        weather_cache_max_entries=2,
    )
    client = FakeClient([response(payload())])
    service = OpenMeteoWeather.from_mapping(
        values,
        client=client,
        clock=time.utc,
        sleeper=time.sleep,
        limiter=ProviderLimiter(time.monotonic, time.sleep),
    )
    try:
        result = service.fetch([POINT], WINDOW, deadline=time.deadline())
        assert (
            service.transport.ledger.daily_limit == 500
            and service.transport.ledger.request_limit == 100
        )
        assert client.calls[0][0] == "https://example.invalid/forecast"
        params = dict(client.calls[0][1])
        assert params["models"] == "gfs_seamless" and params["hourly"].endswith("wind_gusts_10m")
        assert service.transport.ledger.used == 1  # five variables still <=10
        assert (
            result.attribution.provider == "Open-Meteo" and "CC BY 4.0" in result.attribution.text
        )
        assert "processed" in result.attribution.text and result.attribution.source_url
        time.seconds = 10
        assert service.cache.get(service._key(POINT, WINDOW)) is None
    finally:
        service.close()


def test_pooled_coordinate_over_cap_reuses_trip_too_large() -> None:
    time = FakeTime()
    service = adapter(FakeClient([]), time)
    try:
        with pytest.raises(RouteError) as caught:
            service.fetch(points(201), WINDOW, deadline=time.deadline())
        assert caught.value.code == "TRIP_TOO_LARGE"
    finally:
        service.close()


def test_failed_read_timeout_retry_is_not_cached() -> None:
    import httpx

    time = FakeTime()
    client = FakeClient(
        [httpx.ReadTimeout("synthetic"), httpx.ReadTimeout("synthetic"), response(payload())]
    )
    service = adapter(client, time)
    try:
        failed = service.fetch([POINT], WINDOW, deadline=time.deadline())
        assert failed.failed_indices == (0,) and len(client.calls) == 2
        assert service.cache.get(service._key(POINT, WINDOW)) is None
        recovered = service.fetch([POINT], WINDOW, deadline=time.deadline())
        assert recovered.failed_indices == () and recovered.diagnostics.cache_hits == 0
        assert len(client.calls) == 3 and service.transport.ledger.used == 3
    finally:
        service.close()
