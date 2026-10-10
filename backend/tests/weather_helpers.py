"""Invented Open-Meteo structures and injected clocks/clients; never recordings."""

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from fractions import Fraction
from typing import cast

from domain.route_types import Coordinate
from providers.contracts import WeatherSeries, WeatherWindow
from providers.limiter import ProviderLimiter
from providers.quota import QuotaLedger
from providers.transport import HTTPClient, HTTPResponse
from providers.weather import OpenMeteoWeather
from providers.weather_cache import WeatherCache
from providers.weather_normalization import REQUIRED_VARIABLES, normalize_series
from providers.weather_transport import WeatherConfig, WeatherTransport

from tests.provider_helpers import NOW, FakeTime, response

START = int(NOW.timestamp())
WINDOW = WeatherWindow(START, START + 48 * 3600)
POINT = Coordinate(-100, 34)


def payload(window: WeatherWindow = WINDOW, *, wind: object = 12) -> dict[str, object]:
    """Required fields and optional gusts in a synthetic, epoch-keyed hourly payload."""
    hours = window.hours
    return {
        "_fixture": {"provenance": "SYNTHETIC", "live_result": False},
        "timezone": "UTC",
        "utc_offset_seconds": 0,
        "hourly_units": {
            "time": "unixtime",
            "wind_speed_10m": "mp/h",
            "rain": "inch",
            "showers": "inch",
            "snowfall": "inch",
            "wind_gusts_10m": "mp/h",
        },
        "hourly": {
            "time": list(hours),
            "wind_speed_10m": [wind] * len(hours),
            "rain": [0.1] * len(hours),
            "showers": [0.15] * len(hours),
            "snowfall": [0.5] * len(hours),
            "wind_gusts_10m": [55] * len(hours),
        },
    }


def hourly(value: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], value["hourly"])


def units(value: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], value["hourly_units"])


def series(value: object, window: WeatherWindow = WINDOW, *, gusts: bool = False) -> WeatherSeries:
    return normalize_series(value, POINT, window, model="best_match", fetched_at=NOW, gusts=gusts)


def points(count: int) -> tuple[Coordinate, ...]:
    return tuple(Coordinate(-100 + i * 0.02, 34) for i in range(count))


def adapter(
    client: HTTPClient,
    time: FakeTime,
    *,
    config: WeatherConfig | None = None,
    ledger: QuotaLedger | None = None,
    cache: WeatherCache | None = None,
) -> OpenMeteoWeather:
    return OpenMeteoWeather(
        WeatherTransport(
            client,
            time.utc,
            time.sleep,
            ProviderLimiter(time.monotonic, time.sleep),
            ledger if ledger is not None else QuotaLedger(time.utc),
            config if config is not None else WeatherConfig(),
        ),
        cache if cache is not None else WeatherCache(time.utc),
    )


class CoordinateClient:
    """Each coordinate gets its own wind value; batch scheduling cannot change mapping."""

    def __init__(self, window: WeatherWindow = WINDOW) -> None:
        from threading import Lock

        self.window = window
        self.calls: list[tuple[tuple[str, str], ...]] = []
        self.lock = Lock()

    def get(
        self, url: str, *, params: Sequence[tuple[str, str]], timeout: object, deadline: object
    ) -> HTTPResponse:
        with self.lock:
            self.calls.append(tuple(params))
        longitudes = dict(params)["longitude"].split(",")
        locations = [payload(self.window, wind=float(Decimal(x) + 100)) for x in longitudes]
        return response(locations[0] if len(locations) == 1 else locations)


def instant(seconds: int | Fraction) -> datetime:
    return datetime.fromtimestamp(float(seconds), UTC)


VARIABLES = REQUIRED_VARIABLES
