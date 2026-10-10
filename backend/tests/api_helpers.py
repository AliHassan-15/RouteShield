"""Labeled synthetic routing and programmable normalized weather; no HTTP providers."""

import json
import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from math import isfinite
from typing import Any, cast

import pytest
from apps.routing import factory
from apps.routing.schema import ALIASES, SCHEMA
from apps.routing.service import AnalysisService
from django.core.cache import cache
from django.test import Client, override_settings
from domain.geometry import build_route
from domain.route_types import Coordinate, Route
from providers.contracts import (
    PENDING_ATTRIBUTION,
    Candidate,
    GeocodeResult,
    HourlyWeather,
    RoutingResult,
    Unavailable,
    UnavailableReason,
    WeatherDiagnostics,
    WeatherProvenance,
    WeatherResult,
    WeatherSeries,
    WeatherSource,
    WeatherValues,
    WeatherWindow,
)
from providers.deadline import Deadline
from providers.forecast import utc_epoch
from providers.quota import QuotaLedger
from providers.weather import WEATHER_ATTRIBUTION

from tests.route_helpers import straight_route

NOW = datetime(2026, 10, 11, 12, tzinfo=UTC)
ANALYSIS = "/api/v1/route-analysis/"


class FakeClock:
    seconds = 0.0

    def utc(self) -> datetime:
        return NOW + timedelta(seconds=self.seconds)

    def monotonic(self) -> float:
        return self.seconds


def routes(miles: int = 23) -> tuple[Route, ...]:
    base = straight_route(miles)
    return tuple(
        build_route(
            tuple(Coordinate(p.longitude, latitude) for p in base.geometry),
            base.distance_m,
            600 + index * 100,
            cumulative_distances_m=base.cumulative_distances_m,
            cumulative_times_s=(0, 600 + index * 100),
        )
        for index, latitude in enumerate((0.0, 0.02, 0.04))
    )


class FakeGeocoder:
    calls = 0

    def geocode(self, query: str, *, deadline: Deadline) -> GeocodeResult:
        self.calls += 1
        deadline.record_call("geocoding")
        return GeocodeResult(
            (
                Candidate(
                    "synthetic-place",
                    "Synthetic selected place",
                    Coordinate(0, 0),
                    "Synthetic region",
                    "US",
                    "Street",
                    Fraction(1),
                ),
            ),
            PENDING_ATTRIBUTION,
        )


class FakeRouter:
    def __init__(self) -> None:
        self.routes = routes()
        self.calls = 0
        self.effect: Callable[[], None] = lambda: None
        self.deadlines: list[Deadline] = []

    def route_alternatives(
        self,
        origin: Coordinate,
        destination: Coordinate,
        departure: datetime,
        *,
        deadline: Deadline,
    ) -> RoutingResult:
        self.calls += 1
        self.deadlines.append(deadline)
        deadline.record_call("routing")
        self.effect()
        return RoutingResult(self.routes, (), PENDING_ATTRIBUTION, departure, departure)


class FakeWeather:
    """Programmable field depends only on coordinates/forecast hour, never cargo."""

    def __init__(self, clock: FakeClock, ledger: QuotaLedger) -> None:
        self.clock, self.ledger = clock, ledger
        self.value: Callable[[Coordinate, int], WeatherValues | Unavailable] = lambda p, t: (
            WeatherValues(Decimal(0), Decimal(0), Decimal(0))
        )
        self.effect: Callable[[], None] = lambda: None
        self.calls = 0
        self.window: WeatherWindow | None = None
        self.deadlines: list[Deadline] = []
        self.timezone = "America/New_York"
        self.fallback = False
        self.horizon_end: int | None = None
        self.cached = False

    def fetch(
        self, coordinates: Sequence[Coordinate], window: WeatherWindow, *, deadline: Deadline
    ) -> WeatherResult:
        self.calls += 1
        self.window = window
        self.deadlines.append(deadline)
        self.effect()
        deadline.check()
        reservation = None if self.cached else self.ledger.reserve(Fraction(len(coordinates)))
        refused = reservation is None and not self.cached
        if reservation is not None:
            deadline.record_reservation(reservation.units)
            self.ledger.mark_sent(reservation)
            deadline.record_call("weather")
        provenance = WeatherProvenance(
            "Synthetic offline weather",
            "synthetic-v1",
            utc_epoch(self.clock.utc()) - (Fraction(1, 3) if self.cached else 0),
            self.cached,
        )
        source = WeatherSource({}, {"wind": "mph", "rain": "in/hr", "snow": "in/hr"})
        series = []
        for point in coordinates:
            actual_window = (
                window if self.horizon_end is None else replace(window, end_epoch=self.horizon_end)
            )
            hours = {}
            for hour in actual_window.hours:
                value = (
                    Unavailable(UnavailableReason.DEMO_QUOTA_REACHED)
                    if refused
                    else self.value(point, hour)
                )
                hours[hour] = (
                    value
                    if isinstance(value, Unavailable)
                    else HourlyWeather(hour, value, source, provenance)
                )
            series.append(
                WeatherSeries(
                    point, actual_window, hours, provenance, self.timezone, 0, self.fallback
                )
            )
        return WeatherResult(
            tuple(series),
            tuple(range(len(coordinates))) if refused else (),
            WEATHER_ATTRIBUTION,
            WeatherDiagnostics(
                len(coordinates) if self.cached else 0,
                0 if self.cached else len(coordinates),
                (Fraction(1, 3),) if self.cached else (),
                int(not refused and not self.cached),
            ),
        )


def request_body(**overrides: object) -> dict[str, object]:
    return {
        "origin": {"label": "Synthetic origin", "latitude": 0, "longitude": 0},
        "destination": {"label": "Synthetic destination", "latitude": 0, "longitude": 1},
        "departure_time": (NOW + timedelta(minutes=1)).isoformat(),
        "departure_timezone": "UTC",
        "load_weight_lb": 0,
        **overrides,
    }


def schema_check(name: str, value: object) -> None:
    """Validate every nested field/type, rejecting unknowns and non-finite JSON numbers."""
    if name in SCHEMA:
        assert isinstance(value, dict), (name, value)
        spec = SCHEMA[name]
        required = {k for k in spec if not k.endswith("?")}
        allowed = {k.removesuffix("?") for k in spec}
        assert required <= value.keys() <= allowed, (name, value.keys(), required)
        if name == "ExactNumber":
            assert re.fullmatch(r"-?(0|[1-9]\d*)", value["numerator"])
            assert re.fullmatch(r"[1-9]\d*", value["denominator"])
        for key, expression in spec.items():
            key = key.removesuffix("?")
            if key in value:
                schema_check(expression, value[key])
    elif name in ALIASES:
        schema_check(ALIASES[name], value)
    elif " | " in name:
        for expression in name.split(" | "):
            try:
                schema_check(expression, value)
                return
            except AssertionError:
                pass
        raise AssertionError((name, value))
    elif name.endswith("[]"):
        assert isinstance(value, list)
        for item in value:
            schema_check(name[:-2], item)
    elif name.startswith("Record<string, "):
        assert isinstance(value, dict) and all(isinstance(key, str) for key in value)
        for item in value.values():
            schema_check(name[15:-1], item)
    elif name == "[number, number]":
        assert isinstance(value, list) and len(value) == 2
        for item in value:
            schema_check("number", item)
    elif name == "string":
        assert isinstance(value, str)
    elif name == "boolean":
        assert type(value) is bool
    elif name == "number":
        assert type(value) in (int, float) and isfinite(cast(float, value))
    elif name == "null":
        assert value is None
    elif name.startswith('"'):
        assert value == name[1:-1]
    else:
        assert value == int(name)


@dataclass
class Harness:
    client: Client
    service: AnalysisService
    router: FakeRouter
    weather: FakeWeather
    clock: FakeClock

    def post(
        self,
        body: object | None = None,
        *,
        raw: str | None = None,
        content_type: str = "application/json",
        **headers: Any,
    ) -> tuple[int, dict[str, Any]]:
        # Any is confined to test JSON inspection; app outputs pass the recursive schema above.
        response = self.client.post(
            ANALYSIS,
            raw if raw is not None else json.dumps(request_body() if body is None else body),
            content_type=content_type,
            **headers,
        )
        data = cast(dict[str, Any], response.json())
        schema_check("AnalysisResponse" if response.status_code == 200 else "ErrorResponse", data)
        json.dumps(data, allow_nan=False)
        assert response["X-Request-ID"] == "synthetic-request-id"
        return response.status_code, data


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Iterator[Harness]:
    cache.clear()
    clock = FakeClock()
    ledger = QuotaLedger(clock.utc)
    router, geocoder = FakeRouter(), FakeGeocoder()
    weather = FakeWeather(clock, ledger)
    service = AnalysisService(
        geocoder=geocoder,
        router=router,
        weather=weather,
        ledger=ledger,
        clock=clock.utc,
        monotonic=clock.monotonic,
        deadline_factory=lambda: Deadline(35, clock.monotonic),
        request_id=lambda: "synthetic-request-id",
    )
    monkeypatch.setattr(factory, "get_service", lambda: service)
    with override_settings(
        ALLOWED_HOSTS=["testserver"], ANALYSIS_RATE_LIMIT=10000, GEOCODE_RATE_LIMIT=10000
    ):
        yield Harness(Client(), service, router, weather, clock)
    service.close()
    cache.clear()


def ratio(value: dict[str, str]) -> Fraction:
    return Fraction(int(value["numerator"]), int(value["denominator"]))


def hazards(wind: str = "0", rain: str = "0", snow: str = "0") -> WeatherValues:
    return WeatherValues(Decimal(wind), Decimal(rain), Decimal(snow))
