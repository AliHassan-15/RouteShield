"""Bounded synchronous HTTPX transport with a hard caller deadline and no cache."""

import json
import logging
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime
from math import isfinite
from typing import Protocol, cast
from xml.etree import ElementTree

import httpx

from providers.deadline import Deadline
from providers.errors import ErrorCode, ProviderError
from providers.limiter import ProviderLimiter

MAX_BODY_BYTES = 32 * 1024 * 1024
TRANSIENT_STATUSES = frozenset({502, 503, 504})


class _ConnectionFailure(ProviderError):
    """A safe retry marker, without retaining the original connection exception."""


@dataclass(frozen=True, slots=True)
class TransportConfig:
    connect_seconds: float = 3
    routing_read_seconds: float = 25
    geocode_read_seconds: float = 8
    geocode_retries: int = 1
    backoff_seconds: float = 0.5

    def __post_init__(self) -> None:
        values = (self.connect_seconds, self.routing_read_seconds, self.geocode_read_seconds)
        if (
            any(isinstance(v, bool) or not isfinite(v) or v <= 0 for v in values)
            or self.connect_seconds > 3
            or self.routing_read_seconds > 25
            or self.geocode_read_seconds > 8
            or type(self.geocode_retries) is not int
            or not 0 <= self.geocode_retries <= 1
            or isinstance(self.backoff_seconds, bool)
            or not isfinite(self.backoff_seconds)
            or not 0 <= self.backoff_seconds <= 0.5
        ):
            raise ProviderError(ErrorCode.INVALID_REQUEST)


@dataclass(frozen=True, slots=True)
class HTTPResponse:
    status: int
    body: bytes = field(repr=False)
    content_type: str = field(default="application/json", repr=False)
    retry_after: str | None = field(default=None, repr=False)


DEFAULT_TRANSPORT_CONFIG = TransportConfig()


class HTTPClient(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Sequence[tuple[str, str]],
        timeout: httpx.Timeout,
        deadline: Deadline,
    ) -> HTTPResponse:
        """Return bounded ephemeral bytes; implementations must not log requests."""
        ...


class _NoTransportLogs(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # HTTPX INFO includes the entire URL; httpcore DEBUG can include headers.
        return False


def silence_transport_logs() -> None:
    """Suppress library request tracing, including when application DEBUG is enabled."""
    names = {
        "httpx",
        "httpcore",
        "httpcore.connection",
        "httpcore.connection_pool",
        "httpcore.http11",
        "httpcore.http2",
        "httpcore.proxy",
        "httpcore.socks",
    }
    names.update(name for name in logging.Logger.manager.loggerDict if name.startswith("httpcore."))
    for name in names:
        logger = logging.getLogger(name)
        if not any(isinstance(item, _NoTransportLogs) for item in logger.filters):
            logger.addFilter(_NoTransportLogs())


class HttpxClient:
    """Fixed HTTPX options: no proxy inheritance, redirects, HTTP retries or results cache."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(trust_env=False, follow_redirects=False)
        silence_transport_logs()

    def get(
        self,
        url: str,
        *,
        params: Sequence[tuple[str, str]],
        timeout: httpx.Timeout,
        deadline: Deadline,
    ) -> HTTPResponse:
        """Stream bounded bytes and check time between chunks; outer wait is hard-bounded."""
        with self._client.stream(
            "GET", url, params=tuple(params), timeout=timeout, follow_redirects=False
        ) as response:
            body = bytearray()
            for chunk in response.iter_bytes():
                deadline.check()
                body.extend(chunk)
                if len(body) > MAX_BODY_BYTES:
                    raise ProviderError(ErrorCode.MALFORMED_PROVIDER_RESPONSE)
            deadline.check()
            return HTTPResponse(
                response.status_code,
                bytes(body),
                response.headers.get("content-type", ""),
                response.headers.get("retry-after"),
            )

    def close(self) -> None:
        """Release connection resources without persisting response data."""
        self._client.close()


def json_object(response: HTTPResponse) -> dict[str, object]:
    """Require a JSON success object; Decimal avoids binary arithmetic in normalization."""
    result: object = None
    failed = False
    try:
        if len(response.body) > MAX_BODY_BYTES:
            failed = True
        else:
            result = json.loads(response.body, parse_float=Decimal, parse_constant=lambda _: None)
    except (ValueError, RecursionError, UnicodeError):
        failed = True
    media_type = response.content_type.split(";", 1)[0].strip().lower()
    if (
        failed
        or not isinstance(result, dict)
        or not (media_type == "application/json" or media_type.endswith("+json"))
    ):
        raise ProviderError(ErrorCode.MALFORMED_PROVIDER_RESPONSE) from None
    return cast(dict[str, object], result)


def _error_flags(response: HTTPResponse) -> tuple[bool, bool]:
    """Extract two booleans only; never propagate body text or parser exception causes."""
    code = message = ""
    try:
        raw = json.loads(response.body)
        if isinstance(raw, dict):
            detail = raw.get("detailedError", raw.get("error", {}))
            if isinstance(detail, dict):
                code = str(detail.get("code", ""))
                message = str(detail.get("message", ""))
    except (ValueError, RecursionError, UnicodeError):
        try:
            root = ElementTree.fromstring(response.body)
            for node in root.iter():
                name = node.tag.rsplit("}", 1)[-1].lower()
                if name == "code":
                    code = node.text or ""
                if name in {"message", "description"}:
                    message = node.text or ""
        except (ElementTree.ParseError, ValueError, RecursionError):
            pass
    past = ("depart" in message.lower() and "past" in message.lower()) or (
        code == "INVALID_DEPARTURE_TIME" and "past" in message.lower()
    )
    return code == "NO_ROUTE_FOUND", past


def normalized_error(response: HTTPResponse) -> ProviderError:
    """Status-led JSON/XML/empty failures use a closed safe message set."""
    if response.status in {401, 403}:
        return ProviderError(ErrorCode.PROVIDER_AUTH)
    if response.status == 429:
        return ProviderError(ErrorCode.QUOTA_EXCEEDED)
    if response.status in {408, 504}:
        return ProviderError(ErrorCode.PROVIDER_TIMEOUT)
    no_route, past = _error_flags(response)
    if no_route:
        return ProviderError(ErrorCode.NO_ROUTE)
    if response.status in {400, 404, 405, 414, 415, 422}:
        return ProviderError(ErrorCode.INVALID_REQUEST, past_departure_rejected=past)
    return ProviderError(ErrorCode.PROVIDER_UNAVAILABLE)


def retry_delay(value: str | None, now: datetime, backoff: float) -> float:
    """Honor numeric/date Retry-After in full, or skip retry when the deadline cannot fit."""
    if value is None:
        return backoff
    try:
        delay = float(value)
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
            delay = (when - now).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return backoff
    return max(backoff, delay) if isfinite(delay) and delay >= 0 else backoff


class TomTomTransport:
    """Shared limiter/worker pool; no retained response or request cache."""

    def __init__(
        self,
        client: HTTPClient,
        key: str,
        limiter: ProviderLimiter,
        clock: Callable[[], datetime],
        sleeper: Callable[[float], None],
        config: TransportConfig = DEFAULT_TRANSPORT_CONFIG,
    ) -> None:
        self._client, self._key, self._limiter = client, key, limiter
        self._clock, self._sleeper, self.config = clock, sleeper, config
        self._workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix="provider")
        silence_transport_logs()

    def __repr__(self) -> str:
        return "TomTomTransport(credentials=[REDACTED])"

    def _attempt(
        self,
        path: str,
        params: Sequence[tuple[str, str]],
        read: float,
        deadline: Deadline,
    ) -> HTTPResponse:
        error: ProviderError | None = None
        response: HTTPResponse | None = None
        with self._limiter.slot(deadline):
            remaining = deadline.remaining()
            timeout = httpx.Timeout(
                min(read, remaining),
                connect=min(self.config.connect_seconds, remaining),
                pool=min(remaining, 3),
                write=min(remaining, 3),
            )
            try:
                deadline.record_call("routing" if path.startswith("/routing/") else "geocoding")
                response = self._client.get(
                    "https://api.tomtom.com" + path,
                    params=(*params, ("key", self._key)),
                    timeout=timeout,
                    deadline=deadline,
                )
            except ProviderError as safe:
                error = ProviderError(safe.code)
            except httpx.TimeoutException:
                error = ProviderError(ErrorCode.PROVIDER_TIMEOUT)
            except httpx.ConnectError:
                error = _ConnectionFailure(ErrorCode.PROVIDER_UNAVAILABLE)
            except (httpx.NetworkError, OSError):
                error = ProviderError(ErrorCode.PROVIDER_UNAVAILABLE)
            except Exception:
                error = ProviderError(ErrorCode.PROVIDER_UNAVAILABLE)
            # Raise outside except so even __context__ retains no unsafe transport exception.
            if error is not None:
                raise error from None
            deadline.check()
            if response is None:
                raise ProviderError(ErrorCode.PROVIDER_UNAVAILABLE)
            return response

    def get(
        self,
        path: str,
        params: Sequence[tuple[str, str]],
        *,
        routing: bool,
        deadline: Deadline,
    ) -> HTTPResponse:
        """Routing never retries; geocoding retries connection/502/503/504 only once."""
        if not self._key:
            raise ProviderError(ErrorCode.PROVIDER_AUTH)
        attempts = 1 if routing else 1 + self.config.geocode_retries
        read = self.config.routing_read_seconds if routing else self.config.geocode_read_seconds
        for attempt in range(attempts):
            deadline.check()
            future = self._workers.submit(self._attempt, path, params, read, deadline)
            error: ProviderError | None = None
            response: HTTPResponse | None = None
            connection_failure = False
            try:
                response = future.result(timeout=deadline.remaining())
            except FutureTimeout:
                deadline.cancel()
                future.cancel()
                error = ProviderError(ErrorCode.PROVIDER_TIMEOUT)
            except ProviderError as safe:
                error = ProviderError(safe.code)
                connection_failure = isinstance(safe, _ConnectionFailure)
            deadline.check()
            transient = False
            if response is not None:
                if response.status == 200:
                    return response
                error = normalized_error(response)
                transient = response.status in TRANSIENT_STATUSES
            elif error is not None:
                transient = connection_failure
            if error is None:
                error = ProviderError(ErrorCode.PROVIDER_UNAVAILABLE)
            if not transient or attempt + 1 == attempts:
                raise error from None
            delay = retry_delay(
                response.retry_after if response else None,
                self._clock(),
                self.config.backoff_seconds,
            )
            if delay >= deadline.remaining():
                raise error from None
            deadline.sleep(delay, self._sleeper)
        raise ProviderError(ErrorCode.PROVIDER_UNAVAILABLE)

    def close(self) -> None:
        """Cancel queued requests; active calls remain bounded and retain limiter slots."""
        self._workers.shutdown(wait=False, cancel_futures=True)
