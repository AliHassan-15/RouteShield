"""Open-Meteo hourly adapter: mandatory-ordered batches, isolated failures, weather-only cache."""

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import replace
from datetime import UTC, datetime
from fractions import Fraction
from typing import cast

from domain.route_types import Coordinate, RouteError

from providers.contracts import (
    Attribution,
    UnavailableReason,
    WeatherDiagnostics,
    WeatherResult,
    WeatherSeries,
    WeatherWindow,
)
from providers.deadline import Deadline
from providers.errors import ErrorCode, ProviderError
from providers.forecast import series_age, utc_epoch, validate_window
from providers.limiter import ProviderLimiter
from providers.quota import QuotaLedger
from providers.transport import HTTPClient
from providers.weather_cache import WeatherCache, WeatherCacheKey
from providers.weather_normalization import (
    GUST_VARIABLE,
    REQUIRED_VARIABLES,
    normalize_series,
    unavailable_series,
    weather_json,
)
from providers.weather_transport import SendCounter, WeatherConfig, WeatherTransport

WEATHER_ATTRIBUTION = Attribution(
    "Open-Meteo",
    "Weather data by Open-Meteo, CC BY 4.0. Data converted and processed for RouteShield.",
    True,
    "https://open-meteo.com/",
    "https://open-meteo.com/en/licence",
)


class OpenMeteoWeather:
    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, object],
        *,
        client: HTTPClient,
        clock: Callable[[], datetime],
        sleeper: Callable[[float], None],
        limiter: ProviderLimiter,
        ledger: QuotaLedger | None = None,
        cache: WeatherCache | None = None,
    ) -> "OpenMeteoWeather":
        """Compose weather settings and injectable shared resources without framework imports."""
        config = WeatherConfig.from_mapping(values)
        ledger = (
            ledger
            if ledger is not None
            else QuotaLedger(
                clock,
                daily_limit=cast(int, values.get("weather_daily_quota_units", 8000)),
                request_limit=cast(int, values.get("weather_request_unit_limit", 200)),
            )
        )
        cache = (
            cache
            if cache is not None
            else WeatherCache(
                clock,
                ttl_seconds=cast(int, values.get("weather_cache_ttl_seconds", 900)),
                max_entries=cast(int, values.get("weather_cache_max_entries", 400)),
            )
        )
        return cls(WeatherTransport(client, clock, sleeper, limiter, ledger, config), cache)

    def __init__(self, transport: WeatherTransport, cache: WeatherCache) -> None:
        self.transport, self.cache, self.config = transport, cache, transport.config
        self._batches = ThreadPoolExecutor(
            max_workers=self.config.concurrency, thread_name_prefix="weather-batch"
        )

    def _key(self, coordinate: Coordinate, window: WeatherWindow) -> WeatherCacheKey:
        return WeatherCacheKey(
            "Open-Meteo",
            self.config.model,
            self.config.base_url,
            coordinate,
            window,
            (*REQUIRED_VARIABLES, GUST_VARIABLE) if self.config.gusts else REQUIRED_VARIABLES,
            ("mph", "inch", "UTC", "unixtime"),
        )

    def _failure(
        self, coordinate: Coordinate, window: WeatherWindow, reason: UnavailableReason
    ) -> WeatherSeries:
        return unavailable_series(
            coordinate, window, reason, model=self.config.model, fetched_at=self.transport.clock()
        )

    def _batch(
        self,
        coordinates: tuple[Coordinate, ...],
        window: WeatherWindow,
        deadline: Deadline,
        counter: SendCounter,
    ) -> tuple[WeatherSeries, ...]:
        variables = (
            (*REQUIRED_VARIABLES, GUST_VARIABLE) if self.config.gusts else REQUIRED_VARIABLES
        )
        now = self.transport.clock().astimezone(UTC)
        maximum = (
            int(utc_epoch(now.replace(hour=0, minute=0, second=0, microsecond=0)))
            + 16 * 86400
            - 3600
        )
        if window.start_epoch > maximum:
            return tuple(
                self._failure(c, window, UnavailableReason.OUT_OF_HORIZON) for c in coordinates
            )
        request_window = WeatherWindow(window.start_epoch, min(window.end_epoch, maximum))
        params = (
            ("latitude", ",".join(str(c.latitude) for c in coordinates)),
            ("longitude", ",".join(str(c.longitude) for c in coordinates)),
            ("hourly", ",".join(variables)),
            ("wind_speed_unit", "mph"),
            ("precipitation_unit", "inch"),
            ("timezone", "UTC"),
            ("timeformat", "unixtime"),
            (
                "start_hour",
                datetime.fromtimestamp(request_window.start_epoch, UTC).strftime("%Y-%m-%dT%H:%M"),
            ),
            (
                "end_hour",
                datetime.fromtimestamp(request_window.end_epoch, UTC).strftime("%Y-%m-%dT%H:%M"),
            ),
            *((("models", self.config.model),) if self.config.model != "best_match" else ()),
        )
        try:
            response = self.transport.get(
                params,
                window=request_window,
                coordinates=len(coordinates),
                variables=len(variables),
                deadline=deadline,
                counter=counter,
            )
            if isinstance(response, UnavailableReason):
                return tuple(self._failure(c, window, response) for c in coordinates)
            document = weather_json(response)
            locations = document if isinstance(document, list) else [document]
            if len(locations) != len(coordinates):
                raise ProviderError(ErrorCode.MALFORMED_PROVIDER_RESPONSE)
            normalized = []
            for coordinate, item in zip(coordinates, locations, strict=True):
                try:
                    series = normalize_series(
                        item,
                        coordinate,
                        window,
                        model=self.config.model,
                        fetched_at=self.transport.clock(),
                        gusts=self.config.gusts,
                    )
                except ProviderError:
                    series = self._failure(coordinate, window, UnavailableReason.PROVIDER_FAILURE)
                if series.timezone in {"UTC", "GMT", "Etc/UTC", "Etc/GMT"}:
                    # UTC request metadata does not establish a geographic local zone.
                    series = replace(series, timezone_fallback=True)
                normalized.append(series)
            deadline.check()
            for series in normalized:
                self.cache.put(self._key(series.coordinate, window), series)
            return tuple(normalized)
        except ProviderError as error:
            reason = (
                UnavailableReason.QUOTA_EXCEEDED
                if error.code is ErrorCode.QUOTA_EXCEEDED
                else UnavailableReason.PROVIDER_FAILURE
            )
            return tuple(self._failure(c, window, reason) for c in coordinates)

    def fetch(
        self, coordinates: Sequence[Coordinate], window: WeatherWindow, *, deadline: Deadline
    ) -> WeatherResult:
        """Preserve pooled input order; one failed batch never overwrites another."""
        validate_window(window)
        if (
            not isinstance(coordinates, Sequence)
            or not coordinates
            or any(not isinstance(c, Coordinate) for c in coordinates)
            or len(set(coordinates)) != len(coordinates)
        ):
            raise ProviderError(ErrorCode.INVALID_REQUEST)
        if len(coordinates) > self.config.coordinate_cap:
            raise RouteError(
                "TRIP_TOO_LARGE", "Pooled weather coordinates exceed the approved cap."
            )
        if deadline.remaining() <= 0:
            failures = tuple(
                self._failure(c, window, UnavailableReason.PROVIDER_FAILURE) for c in coordinates
            )
            return WeatherResult(
                failures,
                tuple(range(len(coordinates))),
                WEATHER_ATTRIBUTION,
                WeatherDiagnostics(0, 0, tuple(Fraction(0) for _ in coordinates), 0),
            )
        counter = SendCounter()
        output: list[WeatherSeries | None] = [None] * len(coordinates)
        missing = []
        hits = 0
        for i, coordinate in enumerate(coordinates):
            found = self.cache.get(self._key(coordinate, window))
            if found is None:
                missing.append(i)
            else:
                output[i] = found
                hits += 1
        jobs: list[tuple[tuple[int, ...], Future[tuple[WeatherSeries, ...]]]] = []
        for offset in range(0, len(missing), self.config.batch_size):
            indices = tuple(missing[offset : offset + self.config.batch_size])
            points = tuple(coordinates[i] for i in indices)
            jobs.append(
                (indices, self._batches.submit(self._batch, points, window, deadline, counter))
            )
        for indices, future in jobs:
            try:
                batch = future.result(timeout=deadline.remaining())
            except FutureTimeout:
                future.cancel()
                deadline.cancel()
                batch = tuple(
                    self._failure(coordinates[i], window, UnavailableReason.PROVIDER_FAILURE)
                    for i in indices
                )
            except Exception:
                # Untrusted response parsing must not leak transport/body exception text.
                batch = tuple(
                    self._failure(coordinates[i], window, UnavailableReason.PROVIDER_FAILURE)
                    for i in indices
                )
            for index, series in zip(indices, batch, strict=True):
                output[index] = series
        all_series = cast(tuple[WeatherSeries, ...], tuple(output))
        now = self.transport.clock()
        return WeatherResult(
            all_series,
            tuple(i for i, s in enumerate(all_series) if not s.complete),
            WEATHER_ATTRIBUTION,
            WeatherDiagnostics(
                hits, len(missing), tuple(series_age(s, now) for s in all_series), counter.value
            ),
        )

    def close(self) -> None:
        self._batches.shutdown(wait=False, cancel_futures=True)
        self.transport.close()
