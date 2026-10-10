"""Bounded weather I/O; reuse safe provider errors without query/body diagnostics."""

import re
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from threading import Lock
from typing import cast
from urllib.parse import urlsplit

import httpx

from providers.contracts import UnavailableReason, WeatherWindow
from providers.deadline import Deadline
from providers.errors import ErrorCode, ProviderError
from providers.limiter import ProviderLimiter
from providers.quota import QuotaLedger, quota_units
from providers.transport import (
    HTTPClient,
    HTTPResponse,
    normalized_error,
    retry_delay,
    silence_transport_logs,
)


@dataclass(frozen=True, slots=True)
class WeatherConfig:
    base_url: str = field(default="https://api.open-meteo.com/v1/forecast", repr=False)
    model: str = "best_match"
    connect_seconds: float = 3
    read_seconds: float = 8
    retries: int = 1
    backoff_seconds: float = 0.5
    batch_size: int = 50
    concurrency: int = 2
    coordinate_cap: int = 200
    gusts: bool = False

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "WeatherConfig":
        """Consume Django's prepared weather values without importing Django here."""
        return cls(
            base_url=cast(str, values.get("weather_base_url", cls().base_url)),
            model=cast(str, values.get("weather_model", "best_match")),
            connect_seconds=cast(float, values.get("connect_timeout_seconds", 3)),
            read_seconds=cast(float, values.get("weather_timeout_seconds", 8)),
            retries=cast(int, values.get("weather_max_retries", 1)),
            backoff_seconds=cast(float, values.get("weather_retry_backoff_seconds", 0.5)),
            batch_size=cast(int, values.get("batch_size", 50)),
            concurrency=cast(int, values.get("concurrency", 2)),
            coordinate_cap=cast(int, values.get("max_coordinates", 200)),
            gusts=cast(bool, values.get("weather_gusts", False)),
        )

    def __post_init__(self) -> None:
        invalid = False
        try:
            url = urlsplit(self.base_url)
            invalid = (
                url.scheme != "https"
                or not url.netloc
                or bool(url.query)
                or bool(url.fragment)
                or url.username is not None
                or url.password is not None
            )
        except (ValueError, TypeError, AttributeError):
            invalid = True
        if (
            invalid
            or not isinstance(self.model, str)
            or not re.fullmatch(r"[a-z][a-z0-9_]*", self.model)
            or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) or v <= 0
                for v in (self.connect_seconds, self.read_seconds)
            )
            or self.connect_seconds > 3
            or self.read_seconds > 8
            or type(self.retries) is not int
            or not 0 <= self.retries <= 1
            or isinstance(self.backoff_seconds, bool)
            or not isinstance(self.backoff_seconds, (int, float))
            or not isfinite(self.backoff_seconds)
            or not 0 <= self.backoff_seconds <= 0.5
            or type(self.batch_size) is not int
            or not 1 <= self.batch_size <= 50
            or type(self.concurrency) is not int
            or not 1 <= self.concurrency <= 2
            or type(self.coordinate_cap) is not int
            or not 1 <= self.coordinate_cap <= 200
            or type(self.gusts) is not bool
        ):
            raise ProviderError(ErrorCode.INVALID_REQUEST)


class SendCounter:
    def __init__(self) -> None:
        self._lock = Lock()
        self.value = 0

    def increment(self) -> None:
        with self._lock:
            self.value += 1


class _ConnectionFailure(ProviderError):
    pass


class WeatherTransport:
    def __init__(
        self,
        client: HTTPClient,
        clock: Callable[[], datetime],
        sleeper: Callable[[float], None],
        limiter: ProviderLimiter,
        ledger: QuotaLedger,
        config: WeatherConfig,
    ) -> None:
        self.client, self.clock, self.sleeper, self.limiter, self.ledger, self.config = (
            client,
            clock,
            sleeper,
            limiter,
            ledger,
            config,
        )
        self._workers = ThreadPoolExecutor(
            max_workers=config.concurrency, thread_name_prefix="weather-http"
        )
        silence_transport_logs()

    def _attempt(
        self,
        params: Sequence[tuple[str, str]],
        window: WeatherWindow,
        coordinates: int,
        variables: int,
        deadline: Deadline,
        counter: SendCounter,
    ) -> HTTPResponse | UnavailableReason:
        with self.limiter.slot(deadline):
            reservation = self.ledger.reserve(quota_units(coordinates, variables, window))
            if reservation is None:
                return UnavailableReason.DEMO_QUOTA_REACHED
            response: HTTPResponse | None = None
            error: ProviderError | None = None
            try:
                deadline.check()
                remaining = deadline.remaining()
                timeout = httpx.Timeout(
                    min(self.config.read_seconds, remaining),
                    connect=min(self.config.connect_seconds, remaining),
                    pool=min(3, remaining),
                    write=min(3, remaining),
                )
                if not self.ledger.mark_sent(reservation):
                    return UnavailableReason.DEMO_QUOTA_REACHED
                counter.increment()
                response = self.client.get(
                    self.config.base_url, params=params, timeout=timeout, deadline=deadline
                )
            except ProviderError as safe:
                error = ProviderError(safe.code)
            except httpx.TimeoutException:
                error = ProviderError(ErrorCode.PROVIDER_TIMEOUT)
            except httpx.ConnectError:
                error = _ConnectionFailure(ErrorCode.PROVIDER_UNAVAILABLE)
            except Exception:
                error = ProviderError(ErrorCode.PROVIDER_UNAVAILABLE)
            finally:
                self.ledger.release_before_send(reservation)
            if error is not None:
                raise error from None
            deadline.check()
            if response is None:
                raise ProviderError(ErrorCode.PROVIDER_UNAVAILABLE)
            return response

    def get(
        self,
        params: Sequence[tuple[str, str]],
        *,
        window: WeatherWindow,
        coordinates: int,
        variables: int,
        deadline: Deadline,
        counter: SendCounter,
    ) -> HTTPResponse | UnavailableReason:
        """At most one connection/502/503/504 retry; every attempt reserves quota."""
        for attempt in range(1 + self.config.retries):
            deadline.check()
            future = self._workers.submit(
                self._attempt, params, window, coordinates, variables, deadline, counter
            )
            error: ProviderError | None = None
            response: HTTPResponse | UnavailableReason | None = None
            transient = False
            try:
                response = future.result(timeout=deadline.remaining())
            except FutureTimeout:
                future.cancel()
                error = ProviderError(ErrorCode.PROVIDER_TIMEOUT)
            except ProviderError as safe:
                error = ProviderError(safe.code)
                transient = isinstance(safe, _ConnectionFailure)
            deadline.check()
            if isinstance(response, UnavailableReason):
                return response
            if response is not None:
                if response.status == 200:
                    return response
                error = normalized_error(response)
                transient = response.status in {502, 503, 504}
            if error is None:
                error = ProviderError(ErrorCode.PROVIDER_UNAVAILABLE)
            if not transient or attempt == self.config.retries:
                raise error from None
            delay = retry_delay(
                response.retry_after if isinstance(response, HTTPResponse) else None,
                self.clock(),
                self.config.backoff_seconds,
            )
            if delay >= deadline.remaining():
                raise error from None
            deadline.sleep(delay, self.sleeper)
        raise ProviderError(ErrorCode.PROVIDER_UNAVAILABLE)

    def close(self) -> None:
        self._workers.shutdown(wait=False, cancel_futures=True)
