"""TIME/ERROR/ROUTE: bounded attempts, safe failures and injectable clocks."""

import json
import logging
import socket
import threading
import time as real_time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import httpx
import pytest
from providers.deadline import Deadline
from providers.errors import ERROR_MESSAGES, ErrorCode, ProviderError
from providers.limiter import ProviderLimiter
from providers.transport import (
    HTTPResponse,
    HttpxClient,
    TomTomTransport,
    TransportConfig,
    json_object,
    normalized_error,
    retry_delay,
)

from tests.provider_helpers import FAKE_KEY, NOW, FakeClient, FakeTime, response, transport


@pytest.mark.parametrize(
    "status,code",
    [
        (400, ErrorCode.INVALID_REQUEST),
        (401, ErrorCode.PROVIDER_AUTH),
        (403, ErrorCode.PROVIDER_AUTH),
        (404, ErrorCode.INVALID_REQUEST),
        (408, ErrorCode.PROVIDER_TIMEOUT),
        (429, ErrorCode.QUOTA_EXCEEDED),
        (500, ErrorCode.PROVIDER_UNAVAILABLE),
        (502, ErrorCode.PROVIDER_UNAVAILABLE),
        (503, ErrorCode.PROVIDER_UNAVAILABLE),
        (504, ErrorCode.PROVIDER_TIMEOUT),
        (302, ErrorCode.PROVIDER_UNAVAILABLE),
    ],
)
@pytest.mark.parametrize(
    "body,content_type",
    [
        (b'{"error":{"message":"upstream body"}}', "application/json"),
        (b"<error><message>upstream body</message></error>", "application/xml"),
        (b"", "application/json"),
        (b"<broken", "text/xml"),
        (b"not json", "text/plain"),
    ],
)
def test_error_status_body_forms(
    status: int, code: ErrorCode, body: bytes, content_type: str
) -> None:
    error = normalized_error(HTTPResponse(status, body, content_type))
    assert error.code is code and str(error) == ERROR_MESSAGES[code]
    assert "upstream body" not in json.dumps(error.as_dict())


@pytest.mark.parametrize(
    "body",
    [
        b'{"detailedError":{"code":"NO_ROUTE_FOUND","message":"discarded"}}',
        b"<error><code>NO_ROUTE_FOUND</code><message>discarded</message></error>",
    ],
)
def test_no_route_whitelisted_code(body: bytes) -> None:
    assert normalized_error(HTTPResponse(400, body, "misleading/type")).code is ErrorCode.NO_ROUTE


@pytest.mark.parametrize(
    "cause",
    [
        httpx.ConnectError(FAKE_KEY),
        httpx.ReadTimeout(FAKE_KEY),
        httpx.ConnectTimeout(FAKE_KEY),
        httpx.ReadError(FAKE_KEY),
        RuntimeError(FAKE_KEY),
    ],
)
def test_transport_exception_secrecy(cause: Exception, caplog: pytest.LogCaptureFixture) -> None:
    clock = FakeTime()
    client = FakeClient([cause])
    adapter = transport(client, clock)
    caplog.set_level(logging.DEBUG)
    try:
        with pytest.raises(ProviderError) as caught:
            adapter.get(
                "/routing/1/calculateRoute/test/json", [], routing=True, deadline=clock.deadline()
            )
        error = caught.value
        assert error.__cause__ is None and error.__context__ is None
        text = " ".join(
            (
                str(error),
                repr(error),
                json.dumps(error.as_dict()),
                repr(adapter),
                "".join(traceback.format_exception(error)),
                caplog.text,
            )
        )
        assert FAKE_KEY not in text and "https://" not in text
        assert len(client.calls) == 1
    finally:
        adapter.close()


def test_native_httpx_logging_and_response_reprs_are_safe(caplog: pytest.LogCaptureFixture) -> None:
    clock = FakeTime()
    caplog.set_level(logging.DEBUG)

    def handler(request: httpx.Request) -> httpx.Response:
        logging.getLogger("httpcore.connection").debug("unsafe %s", request.url)
        return httpx.Response(401, text=FAKE_KEY, headers={"content-type": "text/xml"})

    native = httpx.Client(transport=httpx.MockTransport(handler), trust_env=False)
    client = HttpxClient(native)
    adapter = TomTomTransport(
        client, FAKE_KEY, ProviderLimiter(clock.monotonic, clock.sleep), clock.utc, clock.sleep
    )
    try:
        with pytest.raises(ProviderError) as caught:
            adapter.get(
                "/routing/1/calculateRoute/test/json", [], routing=True, deadline=clock.deadline()
            )
        assert FAKE_KEY not in caplog.text + repr(caught.value) + json.dumps(caught.value.as_dict())
        assert "https://" not in caplog.text
        assert FAKE_KEY not in repr(HTTPResponse(401, FAKE_KEY.encode(), FAKE_KEY, FAKE_KEY))
    finally:
        adapter.close()
        client.close()


@pytest.mark.parametrize("status", [502, 503, 504])
def test_single_geocoding_status_retry(status: int) -> None:
    clock = FakeTime()
    client = FakeClient([response({}, status), response({})])
    adapter = transport(client, clock)
    try:
        adapter.get("/search/2/geocode/test.json", [], routing=False, deadline=clock.deadline())
        assert len(client.calls) == 2 and clock.sleeps == [0.5]
    finally:
        adapter.close()


def test_geocoding_connection_retry_only() -> None:
    clock = FakeTime()
    client = FakeClient([httpx.ConnectError(FAKE_KEY), response({})])
    adapter = transport(client, clock)
    try:
        adapter.get("/search/2/geocode/test.json", [], routing=False, deadline=clock.deadline())
        assert len(client.calls) == 2 and clock.sleeps == [0.5]
    finally:
        adapter.close()


@pytest.mark.parametrize(
    "failure",
    [
        response({}, 429),
        response({}, 401),
        response({}, 400),
        httpx.ReadTimeout(FAKE_KEY),
        httpx.ConnectTimeout(FAKE_KEY),
        httpx.ReadError(FAKE_KEY),
        RuntimeError(FAKE_KEY),
    ],
)
def test_geocoding_nontransient_never_retries(failure: HTTPResponse | Exception) -> None:
    clock = FakeTime()
    client = FakeClient([failure])
    adapter = transport(client, clock)
    try:
        with pytest.raises(ProviderError):
            adapter.get("/search/2/geocode/test.json", [], routing=False, deadline=clock.deadline())
        assert len(client.calls) == 1 and clock.sleeps == []
    finally:
        adapter.close()


@pytest.mark.parametrize(
    "failure",
    [
        response({}, 502),
        response({}, 503),
        response({}, 504),
        httpx.ReadTimeout(FAKE_KEY),
        httpx.ConnectError(FAKE_KEY),
    ],
)
def test_routing_never_automatically_retries(failure: HTTPResponse | Exception) -> None:
    clock = FakeTime()
    client = FakeClient([failure])
    adapter = transport(client, clock)
    try:
        with pytest.raises(ProviderError):
            adapter.get("/routing/1/test", [], routing=True, deadline=clock.deadline())
        assert len(client.calls) == 1
    finally:
        adapter.close()


@pytest.mark.parametrize(
    "seconds,routing,read,connect",
    [(35, True, 25, 3), (35, False, 8, 3), (2, True, 2, 2), (0.1, False, 0.1, 0.1)],
)
def test_phase_timeouts_bounded_by_remaining(
    seconds: float, routing: bool, read: float, connect: float
) -> None:
    clock = FakeTime()
    client = FakeClient([response({})])
    adapter = transport(client, clock)
    try:
        adapter.get("/test", [], routing=routing, deadline=clock.deadline(seconds))
        timeout = client.calls[0][2]
        assert timeout.read == read and timeout.connect == connect
        assert timeout.pool <= seconds and timeout.write <= seconds  # type: ignore[operator]
    finally:
        adapter.close()


@pytest.mark.parametrize(
    "delay,remaining,calls,sleeps",
    [
        ("2", 5, 2, [2.0]),
        ("10", 5, 1, []),
        (None, 0.4, 1, []),
        ("broken", 5, 2, [0.5]),
        ("-1", 5, 2, [0.5]),
    ],
)
def test_retry_after_respects_deadline(
    delay: str | None, remaining: float, calls: int, sleeps: list[float]
) -> None:
    clock = FakeTime()
    client = FakeClient([response({}, 503, retry_after=delay), response({})])
    adapter = transport(client, clock)
    try:
        if calls == 1:
            with pytest.raises(ProviderError):
                adapter.get("/test", [], routing=False, deadline=clock.deadline(remaining))
        else:
            adapter.get("/test", [], routing=False, deadline=clock.deadline(remaining))
        assert len(client.calls) == calls and clock.sleeps == sleeps
    finally:
        adapter.close()


def test_retry_after_date_and_invalid_metadata() -> None:
    assert retry_delay("Sat, 10 Oct 2026 12:00:02 GMT", NOW, 0.5) == 2
    for value in ("NaN", "inf", "-1", "invalid"):
        assert retry_delay(value, NOW, 0.5) == 0.5
    assert retry_delay("Sat, 10 Oct 2026 12:00:02 GMT", NOW + timedelta(seconds=10), 0.5) == 0.5


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True, 36])
def test_invalid_deadline(value: float) -> None:
    with pytest.raises(ProviderError):
        Deadline(value, lambda: 0)


def test_exhausted_shared_deadline_and_sleep() -> None:
    clock = FakeTime()
    deadline = clock.deadline(1)
    deadline.sleep(0.5, clock.sleep)
    assert deadline.remaining() == 0.5
    with pytest.raises(ProviderError):
        deadline.sleep(0.5, clock.sleep)
    clock.seconds = 1
    with pytest.raises(ProviderError):
        deadline.check()


def test_no_late_success_from_injected_client() -> None:
    clock = FakeTime()

    class SlowClient(FakeClient):
        def get(
            self, url: str, *, params: object, timeout: httpx.Timeout, deadline: Deadline
        ) -> HTTPResponse:
            clock.seconds = 36
            return response({})

    adapter = transport(SlowClient([]), clock)
    try:
        with pytest.raises(ProviderError) as caught:
            adapter.get("/test", [], routing=True, deadline=clock.deadline())
        assert caught.value.code is ErrorCode.PROVIDER_TIMEOUT
    finally:
        adapter.close()


def test_hard_caller_deadline_and_concurrency_survive_blocked_transport() -> None:
    entered = threading.Event()
    release = threading.Event()
    lock = threading.Lock()
    active = maximum = 0

    class BlockingClient:
        def get(
            self, url: str, *, params: object, timeout: httpx.Timeout, deadline: Deadline
        ) -> HTTPResponse:
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(active, maximum)
            entered.set()
            release.wait(1)
            with lock:
                active -= 1
            return response({})

    limiter = ProviderLimiter(real_time.monotonic, real_time.sleep)
    adapter = TomTomTransport(BlockingClient(), FAKE_KEY, limiter, lambda: NOW, real_time.sleep)

    def call() -> ErrorCode:
        try:
            adapter.get("/test", [], routing=True, deadline=Deadline(0.1, real_time.monotonic))
        except ProviderError as error:
            return error.code
        raise AssertionError("Late success")

    start = real_time.monotonic()
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(call) for _ in range(3)]
            assert entered.wait(0.5)
            assert all(f.result() == ErrorCode.PROVIDER_TIMEOUT for f in futures)
        assert real_time.monotonic() - start < 0.8 and maximum <= 2
    finally:
        release.set()
        adapter.close()


def test_five_starts_per_rolling_second() -> None:
    clock = FakeTime()
    limiter = ProviderLimiter(clock.monotonic, clock.sleep)
    starts = []
    for _ in range(16):
        with limiter.slot(clock.deadline()):
            starts.append(clock.seconds)
    assert starts == [0] * 5 + [1] * 5 + [2] * 5 + [3]
    assert all(sum(t <= v < t + 1 for v in starts) <= 5 for t in starts)


@pytest.mark.parametrize("qps,concurrency", [(6, 2), (0, 2), (True, 2), (5, 3), (5, 0)])
def test_limiter_invalid_bounds(qps: int, concurrency: int) -> None:
    with pytest.raises(ProviderError):
        ProviderLimiter(lambda: 0, lambda _: None, requests_per_second=qps, concurrency=concurrency)


@pytest.mark.parametrize(
    "body,content_type",
    [
        (b"null", "application/json"),
        (b"[]", "application/json"),
        (b"{", "application/json"),
        (b"{}", "text/xml"),
        (b"", "application/json"),
    ],
)
def test_success_requires_json_object(body: bytes, content_type: str) -> None:
    with pytest.raises(ProviderError) as caught:
        json_object(HTTPResponse(200, body, content_type))
    assert caught.value.code is ErrorCode.MALFORMED_PROVIDER_RESPONSE


def test_normal_suite_socket_guard() -> None:
    with pytest.raises(AssertionError, match="Network access"):
        socket.create_connection(("example.com", 443))


@pytest.mark.parametrize(
    "field,value",
    [
        ("connect_seconds", 3.01),
        ("routing_read_seconds", 25.01),
        ("geocode_read_seconds", 8.01),
        ("connect_seconds", 0),
        ("connect_seconds", True),
        ("routing_read_seconds", float("nan")),
        ("geocode_read_seconds", float("inf")),
        ("geocode_retries", 2),
        ("geocode_retries", True),
        ("backoff_seconds", 0.5001),
        ("backoff_seconds", -1),
    ],
)
def test_transport_config_enforces_contract_caps(field: str, value: object) -> None:
    with pytest.raises(ProviderError) as caught:
        TransportConfig(**{field: value})  # type: ignore[arg-type]
    assert caught.value.code is ErrorCode.INVALID_REQUEST


def test_missing_key_fails_without_request() -> None:
    clock, client = FakeTime(), FakeClient([])
    adapter = TomTomTransport(
        client, "", ProviderLimiter(clock.monotonic, clock.sleep), clock.utc, clock.sleep
    )
    try:
        with pytest.raises(ProviderError) as caught:
            adapter.get("/test", [], routing=True, deadline=clock.deadline())
        assert caught.value.code is ErrorCode.PROVIDER_AUTH
        assert not client.calls
    finally:
        adapter.close()


@pytest.mark.parametrize(
    "status,headers,code",
    [
        (200, {}, ErrorCode.MALFORMED_PROVIDER_RESPONSE),
        (302, {"location": "https://example.com/?key=" + FAKE_KEY}, ErrorCode.PROVIDER_UNAVAILABLE),
    ],
)
def test_native_stream_limit_and_redirect_are_safe(
    monkeypatch: pytest.MonkeyPatch, status: int, headers: dict[str, str], code: ErrorCode
) -> None:
    import providers.transport as module

    clock = FakeTime()
    monkeypatch.setattr(module, "MAX_BODY_BYTES", 20)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, content=b"x" * 21 if status == 200 else b"", headers=headers)

    native = HttpxClient(httpx.Client(transport=httpx.MockTransport(handler), trust_env=False))
    adapter = TomTomTransport(
        native, FAKE_KEY, ProviderLimiter(clock.monotonic, clock.sleep), clock.utc, clock.sleep
    )
    try:
        with pytest.raises(ProviderError) as caught:
            adapter.get("/test", [], routing=True, deadline=clock.deadline())
        assert caught.value.code is code
        assert FAKE_KEY not in repr(caught.value) and len(calls) == 1
        assert caught.value.__context__ is None
    finally:
        adapter.close()
        native.close()
