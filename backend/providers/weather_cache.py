"""Weather-only normalized series cache: exact keys, complete required hours, TTL<=15min."""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
from threading import Lock
from types import MappingProxyType

from domain.route_types import Coordinate

from providers.contracts import HourlyWeather, WeatherSeries, WeatherWindow
from providers.errors import ErrorCode, ProviderError
from providers.forecast import WEATHER_TTL_SECONDS, series_age


@dataclass(frozen=True, slots=True)
class WeatherCacheKey:
    provider: str
    model: str
    source: str = field(repr=False)
    coordinate: Coordinate
    window: WeatherWindow
    variables: tuple[str, ...]
    units: tuple[str, ...]


class WeatherCache:
    def __init__(
        self,
        clock: Callable[[], datetime],
        *,
        ttl_seconds: int = WEATHER_TTL_SECONDS,
        max_entries: int = 400,
    ) -> None:
        if (
            type(ttl_seconds) is not int
            or not 1 <= ttl_seconds <= WEATHER_TTL_SECONDS
            or type(max_entries) is not int
            or max_entries < 1
        ):
            raise ProviderError(ErrorCode.INVALID_REQUEST)
        self._clock, self._ttl, self._max = clock, ttl_seconds, max_entries
        self._entries: dict[WeatherCacheKey, WeatherSeries] = {}
        self._lock = Lock()
        self.hits = self.misses = 0

    def get(self, key: WeatherCacheKey) -> WeatherSeries | None:
        with self._lock:
            series = self._entries.get(key)
            if series is not None and series_age(series, self._clock()) < self._ttl:
                self.hits += 1
                provenance = replace(series.provenance, cache_hit=True)
                hours = MappingProxyType(
                    {
                        t: replace(row, provenance=provenance)
                        if isinstance(row, HourlyWeather)
                        else row
                        for t, row in series.hours.items()
                    }
                )
                return replace(series, provenance=provenance, hours=hours)
            self._entries.pop(key, None)
            self.misses += 1
            return None

    def put(self, key: WeatherCacheKey, series: WeatherSeries) -> None:
        """Never put failures/partial series; immutable normalized objects only."""
        if not series.complete:
            return
        with self._lock:
            if len(self._entries) >= self._max and key not in self._entries:
                self._entries.pop(next(iter(self._entries)))
            self._entries[key] = series
