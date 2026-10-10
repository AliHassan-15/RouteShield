"""WX-09, API-03/08, TIME-01/02, QUOTA-01: retries never escape the shared budget."""

import logging
import threading
import time as real_time
import traceback
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from fractions import Fraction

import httpx
import pytest
from providers.contracts import UnavailableReason
from providers.deadline import Deadline
from providers.errors import ERROR_MESSAGES, ErrorCode, ProviderError
from providers.limiter import ProviderLimiter
from providers.quota import QuotaLedger, Reservation
from providers.transport import HTTPResponse
from providers.weather_transport import SendCounter, WeatherConfig, WeatherTransport

from tests.provider_helpers import NOW, FakeClient, FakeTime, response
from tests.weather_helpers import WINDOW


def transport(
    client: FakeClient,
    time: FakeTime,
    *,
    config: WeatherConfig | None = None,
    ledger: QuotaLedger | None = None,
) -> WeatherTransport:
    return WeatherTransport(
        client,
        time.utc,
        time.sleep,
        ProviderLimiter(time.monotonic, time.sleep),
        ledger if ledger is not None else QuotaLedger(time.utc),
        config if config is not None else WeatherConfig(),
    )


def get(
    worker: WeatherTransport, deadline: Deadline, *, count: int = 50
) -> HTTPResponse | UnavailableReason:
    return worker.get(
        (), window=WINDOW, coordinates=count, variables=4, deadline=deadline, counter=SendCounter()
    )


@pytest.mark.parametrize(
    "failure",
    [httpx.ConnectError("secret URL"), response({}, 502), response({}, 503), response({}, 504)],
)
def test_one_transient_retry_backoff_and_charge(failure: Exception | HTTPResponse) -> None:
    time = FakeTime()
    client = FakeClient([failure, response({})])
    worker = transport(client, time)
    try:
        assert isinstance(get(worker, time.deadline()), HTTPResponse)
        assert len(client.calls) == 2 and time.sleeps == [0.5]
        assert worker.ledger.used == 100
    finally:
        worker.close()


@pytest.mark.parametrize(
    "status,code",
    [
        (400, ErrorCode.INVALID_REQUEST),
        (401, ErrorCode.PROVIDER_AUTH),
        (403, ErrorCode.PROVIDER_AUTH),
        (404, ErrorCode.INVALID_REQUEST),
        (429, ErrorCode.QUOTA_EXCEEDED),
        (500, ErrorCode.PROVIDER_UNAVAILABLE),
        (302, ErrorCode.PROVIDER_UNAVAILABLE),
    ],
)
@pytest.mark.parametrize(
    "body,media",
    [
        (b'{"error":true,"reason":"secret URL"}', "application/json"),
        (b"<error><message>secret URL</message></error>", "application/xml"),
        (b"", ""),
    ],
)
def test_no_retry_fixed_safe_errors_all_body_formats(
    status: int, code: ErrorCode, body: bytes, media: str
) -> None:
    time = FakeTime()
    client = FakeClient([HTTPResponse(status, body, media)])
    worker = transport(client, time)
    try:
        with pytest.raises(ProviderError) as caught:
            get(worker, time.deadline())
        assert caught.value.code is code
        assert str(caught.value) == ERROR_MESSAGES[code]
        assert caught.value.__context__ is None and caught.value.__cause__ is None
        assert len(client.calls) == 1 and time.sleeps == [] and worker.ledger.used == 50
    finally:
        worker.close()


@pytest.mark.parametrize("delay", ["0.25", "1", "invalid", "-1"])
def test_retry_after_fit_and_default_backoff(delay: str) -> None:
    time = FakeTime()
    client = FakeClient([response({}, 503, retry_after=delay), response({})])
    worker = transport(client, time)
    try:
        get(worker, time.deadline())
        expected = 1 if delay == "1" else 0.5  # Retry-After never shortens the base backoff.
        assert time.sleeps == [expected] and len(client.calls) == 2
    finally:
        worker.close()


def test_retry_after_too_long_and_second_failure_stop() -> None:
    for retry_after, responses in [
        ("35", [response({}, 503, retry_after="35")]),
        (None, [response({}, 503), response({}, 503)]),
    ]:
        time = FakeTime()
        client = FakeClient(responses)
        worker = transport(client, time)
        try:
            with pytest.raises(ProviderError):
                get(worker, time.deadline())
            assert len(client.calls) == (1 if retry_after else 2)
        finally:
            worker.close()


@pytest.mark.parametrize(
    "failure", [httpx.ReadTimeout("secret"), httpx.ConnectTimeout("secret"), ValueError("secret")]
)
def test_timeout_and_unexpected_transport_errors_never_retry_or_leak(failure: Exception) -> None:
    time = FakeTime()
    client = FakeClient([failure])
    worker = transport(client, time)
    try:
        with pytest.raises(ProviderError) as caught:
            get(worker, time.deadline())
        assert len(client.calls) == 1 and "secret" not in str(caught.value)
        assert caught.value.__context__ is None
    finally:
        worker.close()


def test_phase_timeouts_clamped_to_remaining_deadline() -> None:
    time = FakeTime()
    client = FakeClient([response({}), response({})])
    worker = transport(client, time)
    try:
        get(worker, time.deadline())
        get(worker, time.deadline(2))
        assert client.calls[0][2].connect == 3 and client.calls[0][2].read == 8
        assert client.calls[1][2].connect == 2 and client.calls[1][2].read == 2
    finally:
        worker.close()


def test_daily_limit_exact_boundary_then_demo_quota_no_send() -> None:
    time = FakeTime()
    client = FakeClient([response({})])
    ledger = QuotaLedger(time.utc, daily_limit=50, request_limit=50)
    worker = transport(client, time, ledger=ledger)
    try:
        assert isinstance(get(worker, time.deadline()), HTTPResponse)
        assert get(worker, time.deadline()) is UnavailableReason.DEMO_QUOTA_REACHED
        assert len(client.calls) == 1 and ledger.used == 50
    finally:
        worker.close()


def test_per_request_guard_and_retry_budget_refusal() -> None:
    time = FakeTime()
    worker = transport(FakeClient([]), time, ledger=QuotaLedger(time.utc, request_limit=49))
    try:
        assert get(worker, time.deadline()) is UnavailableReason.DEMO_QUOTA_REACHED
        assert worker.ledger.used == 0
    finally:
        worker.close()
    client = FakeClient([response({}, 503)])
    worker = transport(client, time, ledger=QuotaLedger(time.utc, daily_limit=50))
    try:
        assert get(worker, time.deadline()) is UnavailableReason.DEMO_QUOTA_REACHED
        assert len(client.calls) == 1 and worker.ledger.used == 50
    finally:
        worker.close()


def test_reservation_released_if_deadline_expires_before_send() -> None:
    time = FakeTime()

    class ExpiringLedger(QuotaLedger):
        def reserve(self, units: Fraction) -> Reservation | None:
            reservation = super().reserve(units)
            time.seconds += 35
            return reservation

    ledger = ExpiringLedger(time.utc)
    client = FakeClient([])
    worker = transport(client, time, ledger=ledger)
    try:
        with pytest.raises(ProviderError):
            get(worker, time.deadline())
        assert ledger.used == 0 and not client.calls
    finally:
        worker.close()


def test_expired_deadline_does_no_work() -> None:
    time = FakeTime()
    deadline = time.deadline()
    time.seconds = 35
    client = FakeClient([])
    worker = transport(client, time)
    try:
        with pytest.raises(ProviderError):
            get(worker, deadline)
        assert worker.ledger.used == 0 and not client.calls
    finally:
        worker.close()


def test_hard_deadline_retains_worker_slots_until_http_finishes() -> None:
    entered, release = threading.Event(), threading.Event()

    class SlowClient:
        def get(
            self,
            url: str,
            *,
            params: Sequence[tuple[str, str]],
            timeout: httpx.Timeout,
            deadline: Deadline,
        ) -> HTTPResponse:
            entered.set()
            release.wait(2)
            return response({})

    limiter = ProviderLimiter(real_time.monotonic, real_time.sleep)
    worker = WeatherTransport(
        SlowClient(),
        lambda: NOW,
        real_time.sleep,
        limiter,
        QuotaLedger(lambda: NOW),
        WeatherConfig(retries=0),
    )
    try:
        with ThreadPoolExecutor(max_workers=1) as caller:
            future = caller.submit(get, worker, Deadline(0.05, real_time.monotonic))
            assert entered.wait(1)
            with pytest.raises(ProviderError):
                future.result(timeout=1)
        assert worker.ledger.used == 50
    finally:
        release.set()
        worker.close()


def test_transport_log_and_traceback_secrecy(caplog: pytest.LogCaptureFixture) -> None:
    secret = "https://secret.invalid/path?api_key=private&latitude=33,34"
    time = FakeTime()
    client = FakeClient([httpx.ConnectError(secret), httpx.ConnectError(secret)])
    worker = transport(client, time)
    try:
        with caplog.at_level(logging.DEBUG):
            logging.getLogger("httpx").info(secret)
            logging.getLogger("httpcore.connection").debug(secret)
            with pytest.raises(ProviderError) as caught:
                get(worker, time.deadline())
        rendered = "".join(traceback.format_exception(caught.value))
        assert secret not in rendered and secret not in caplog.text
        assert secret not in repr(worker.config)
    finally:
        worker.close()


@pytest.mark.parametrize(
    "field,bad",
    [
        ("base_url", "http://unsafe.invalid"),
        ("base_url", "https://unsafe.invalid/?secret=x"),
        ("base_url", "https://u:p@example.invalid"),
        ("model", "a,b"),
        ("model", None),
        ("connect_seconds", 4),
        ("read_seconds", 9),
        ("retries", 2),
        ("retries", True),
        ("backoff_seconds", 0.51),
        ("backoff_seconds", float("nan")),
        ("batch_size", 51),
        ("concurrency", 3),
        ("coordinate_cap", 201),
        ("gusts", 1),
    ],
)
def test_config_rejects_unsafe_bounds(field: str, bad: object) -> None:
    # Runtime boundary deliberately bypasses annotations; errors must still be typed/safe.
    with pytest.raises(ProviderError):
        replace(WeatherConfig(), **{field: bad})  # type: ignore[arg-type]
