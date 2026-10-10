"""Safe errors, deadline bounds, DRF throttles, explicit proxies and private logging."""

import json
import logging
import time
from threading import Event
from typing import Any

import pytest
from apps.routing.errors import ERRORS, APIError
from apps.routing.schema import check_typescript, render_typescript
from apps.routing.service import COMPLETION_MARGIN_SECONDS
from django.test import override_settings
from providers.deadline import Deadline
from providers.errors import ErrorCode, ProviderError

from tests.api_helpers import ANALYSIS, Harness, request_body, schema_check
from tests.api_helpers import api as api


@pytest.mark.parametrize("code", list(ErrorCode))
@pytest.mark.parametrize("endpoint", ["analysis", "geocode"])
def test_typed_provider_mapping(
    api: Harness, code: ErrorCode, endpoint: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: object, **kwargs: object) -> Any:
        raise ProviderError(code)

    if endpoint == "analysis":
        api.router.effect = lambda: fail()
        status, data = api.post()
        assert api.router.calls == 1  # routing timeouts never cause API retry
    else:
        monkeypatch.setattr(api.service.geocoder, "geocode", fail)
        response = api.client.get("/api/v1/geocode/?q=Synthetic")
        status, data = response.status_code, response.json()
        schema_check("ErrorResponse", data)
    expected = "VALIDATION_ERROR" if code is ErrorCode.INVALID_REQUEST else code.value
    assert status == ERRORS[expected][0] and data["error"]["code"] == expected


@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError("https://unsafe.invalid?key=SECRET"),
        ValueError("private address and label"),
        ZeroDivisionError(),
    ],
)
def test_unknown_failure_never_disclosed(api: Harness, failure: Exception) -> None:
    def fail() -> None:
        raise failure

    api.router.effect = fail
    status, data = api.post()
    assert status == 500 and data["error"]["code"] == "INTERNAL_ERROR"
    assert data["error"]["details"] == {}
    assert "unsafe" not in json.dumps(data) and "private" not in json.dumps(data)


@pytest.mark.parametrize(
    "where", ["before_routing", "during_routing", "before_weather", "during_weather"]
)
def test_shared_fake_clock_deadline(
    api: Harness, where: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    if where == "before_routing":

        def begin() -> Deadline:
            deadline = Deadline(35, api.clock.monotonic)
            api.clock.seconds += 35
            return deadline

        api.service.deadline_factory = begin
    elif where == "during_routing":
        api.router.effect = lambda: setattr(api.clock, "seconds", 35)
    elif where == "before_weather":
        original_pool = __import__(
            "apps.routing.service", fromlist=["pool_coordinates"]
        ).pool_coordinates

        def pool(*args: Any, **kwargs: Any) -> Any:
            result = original_pool(*args, **kwargs)
            api.clock.seconds += 35
            return result

        monkeypatch.setattr("apps.routing.service.pool_coordinates", pool)
    else:
        api.weather.effect = lambda: setattr(api.clock, "seconds", 35)
    status, data = api.post()
    if where in ("before_routing", "during_routing"):
        assert status == 504 and data["error"]["code"] == "DEADLINE_EXCEEDED"
    else:
        assert status == 200 and data["recommendation_status"] == "ALL_INCOMPLETE"
        assert "DEADLINE_WEATHER_UNAVAILABLE" in {w["code"] for w in data["warnings"]}
        assert all(r["travel_status"] == "INCOMPLETE" for r in data["routes"])
    assert api.weather.calls == int(where == "during_weather")


@pytest.mark.parametrize("where", ["routing", "weather"])
def test_blocked_adapter_wall_time_bound(api: Harness, where: str) -> None:
    release = Event()
    api.service.monotonic = time.monotonic
    api.service.deadline_factory = lambda: Deadline(0.05, time.monotonic)
    api.service.deadline_seconds = 0.05
    provider = api.router if where == "routing" else api.weather

    def block() -> None:
        release.wait(2)

    provider.effect = block
    start = time.monotonic()
    try:
        status, data = api.post()
        elapsed = time.monotonic() - start
        assert elapsed < 0.05 + COMPLETION_MARGIN_SECONDS
        assert status == (504 if where == "routing" else 200)
        assert data.get("recommendation_status") == (
            "ALL_INCOMPLETE" if where == "weather" else None
        )
    finally:
        release.set()


@pytest.mark.parametrize(
    "endpoint,setting", [(ANALYSIS, "ANALYSIS"), ("/api/v1/geocode/?q=Synthetic", "GEOCODE")]
)
def test_endpoint_throttle_retry_after(api: Harness, endpoint: str, setting: str) -> None:
    with override_settings(**{setting + "_RATE_LIMIT": 1, setting + "_RATE_WINDOW_SECONDS": 60}):

        def call() -> Any:
            return (
                api.client.post(
                    endpoint, json.dumps(request_body()), content_type="application/json"
                )
                if setting == "ANALYSIS"
                else api.client.get(endpoint)
            )

        assert call().status_code == 200
        response = call()
        assert response.status_code == 429 and response.json()["error"]["code"] == "THROTTLED"
        assert 1 <= int(response["Retry-After"]) <= 60
        schema_check("ErrorResponse", response.json())
        # Separate scopes: one endpoint's quota does not exhaust the other endpoint.
        other = (
            api.client.get("/api/v1/geocode/?q=Synthetic")
            if setting == "ANALYSIS"
            else api.client.post(
                ANALYSIS, json.dumps(request_body()), content_type="application/json"
            )
        )
        assert other.status_code == 200


@pytest.mark.parametrize(
    "trusted,peer,forwarded,second_forwarded,blocked",
    [
        ((), "192.0.2.1", "198.51.100.1", "198.51.100.2", True),
        (("192.0.2.0/24",), "192.0.2.1", "198.51.100.1", "198.51.100.2", False),
        (
            ("192.0.2.0/24",),
            "192.0.2.1",
            "198.51.100.1, 192.0.2.2",
            "198.51.100.1, 192.0.2.3",
            True,
        ),
        (("192.0.2.0/24",), "203.0.113.1", "198.51.100.1", "198.51.100.2", True),
        (("192.0.2.0/24",), "192.0.2.1", "garbage", "garbage", True),
    ],
)
def test_proxy_handling(
    api: Harness,
    trusted: tuple[str, ...],
    peer: str,
    forwarded: str,
    second_forwarded: str,
    blocked: bool,
) -> None:
    with override_settings(ANALYSIS_RATE_LIMIT=1, API_TRUSTED_PROXY_CIDRS=trusted):
        assert api.post(HTTP_X_FORWARDED_FOR=forwarded, REMOTE_ADDR=peer)[0] == 200
        assert api.post(HTTP_X_FORWARDED_FOR=second_forwarded, REMOTE_ADDR=peer)[0] == (
            429 if blocked else 200
        )


def test_structured_logging_redacts_inputs(api: Harness, caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("routeshield.requests")
    assert logger.isEnabledFor(logging.INFO) and not logger.propagate
    logger.addHandler(caplog.handler)
    try:
        api.post(
            request_body(
                origin={
                    "label": "Private street SECRET",
                    "latitude": 12.3456789,
                    "longitude": 67.8901234,
                }
            ),
            HTTP_AUTHORIZATION="secret-header",
            HTTP_X_REQUEST_ID="forged-secret-id",
        )
    finally:
        logger.removeHandler(caplog.handler)
    records = [r for r in caplog.records if r.name == "routeshield.requests"]
    assert len(records) == 1
    raw = records[0].getMessage()
    for forbidden in (
        "SECRET",
        "Private",
        "12.3456789",
        "67.8901234",
        "http",
        "secret-header",
        "forged-secret-id",
    ):
        assert forbidden not in raw
    data = json.loads(raw)
    assert set(data) == {
        "request_id",
        "route_name",
        "status",
        "total_ms",
        "stage_ms",
        "provider_calls",
    }
    assert data["route_name"] == "route_analysis" and data["status"] == 422


@pytest.mark.parametrize(
    "endpoint,method,status,schema",
    [
        ("/api/v1/geocode/?q=Synthetic", "get", 200, "GeocodeResponse"),
        ("/api/v1/geocode/?q=xx", "get", 400, "ErrorResponse"),
        ("/api/v1/geocode/?q=Synthetic&url=https://unsafe.invalid", "get", 400, "ErrorResponse"),
        ("/api/v1/geocode/?q=aaa&q=bbb", "get", 400, "ErrorResponse"),
        ("/api/v1/geocode/", "post", 405, "ErrorResponse"),
        (ANALYSIS, "get", 405, "ErrorResponse"),
        ("/api/v1/health/", "get", 200, "HealthResponse"),
        ("/api/v1/health/?ready=1", "get", 200, "HealthResponse"),
        ("/api/v1/nonexistent/", "get", 404, "ErrorResponse"),
    ],
)
def test_endpoint_shapes(
    api: Harness, endpoint: str, method: str, status: int, schema: str
) -> None:
    response = getattr(api.client, method)(endpoint)
    assert response.status_code == status
    schema_check(schema, response.json())
    assert response["X-Request-ID"] and response["Cache-Control"] == "no-store"


@pytest.mark.parametrize("code", list(ERRORS))
def test_all_error_schema_and_safe_messages(code: str) -> None:
    schema_check("ErrorResponse", APIError(code).envelope())
    assert "http" not in ERRORS[code][1]


@pytest.mark.parametrize(
    "scenario,code",
    [
        ("all_clear", "SIMULATION_DISABLED"),
        ("invented", "INVALID_SCENARIO"),
        (["unsafe"], "INVALID_SCENARIO"),
    ],
)
def test_reserved_simulation_explicit_error_identity(
    api: Harness, scenario: object, code: str
) -> None:
    status, data = api.post(request_body(simulation_scenario=scenario))
    assert status == 400 and data["error"]["code"] == code and data["is_simulation"]
    assert data["simulation_scenario"] == ("all_clear" if scenario == "all_clear" else None)
    assert api.router.calls == 0


def test_shared_types_no_drift() -> None:
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api" / "types.ts"
    check_typescript(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("operation", ["add", "remove"])
@pytest.mark.parametrize("side", ["python", "typescript"])
def test_drift_detector_rejects_one_sided_changes(operation: str, side: str) -> None:
    from apps.routing.schema import SCHEMA

    schema = {name: dict(fields) for name, fields in SCHEMA.items()}
    current = render_typescript()
    if side == "python":
        if operation == "add":
            schema["Metadata"]["new_field"] = "string"
        else:
            del schema["Metadata"]["request_id"]
        changed = render_typescript(schema)
    else:
        changed = (
            current.replace(
                "export interface Metadata {", "export interface Metadata {\n  new_field: string;"
            )
            if operation == "add"
            else current.replace("  request_id: string;\n", "")
        )
    with pytest.raises(ValueError, match="contract drift"):
        if side == "python":
            check_typescript(current, schema)
        else:
            check_typescript(changed)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_serialization_rejects_nonfinite(value: float) -> None:
    from apps.routing.serialization import public

    with pytest.raises(ValueError):
        public(value)


def test_completed_partial_weather_survives_deadline(
    api: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    from decimal import Decimal

    from providers.contracts import Unavailable, UnavailableReason, WeatherValues

    original = api.weather.fetch
    api.weather.value = lambda p, t: (
        Unavailable(
            UnavailableReason.MISSING_FIELD, ("rain",), WeatherValues(Decimal(55), None, Decimal(0))
        )
        if round(p.latitude, 2) == 0
        else Unavailable(UnavailableReason.PROVIDER_FAILURE)
    )

    def partial(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        api.clock.seconds = 35
        return result

    monkeypatch.setattr(api.weather, "fetch", partial)
    status, data = api.post()
    assert status == 200
    assert any(r["travel_status"] == "BLOCKED" for r in data["routes"])
    assert any(cp["risk"]["known_blocked"] for r in data["routes"] for cp in r["checkpoints"])


def test_simulation_identity_on_throttle(api: Harness) -> None:
    with override_settings(ANALYSIS_RATE_LIMIT=1):
        assert api.post()[0] == 200
        status, data = api.post(request_body(simulation_scenario="all_clear"))
        assert status == 429 and data["is_simulation"] is True
        assert data["simulation_scenario"] == "all_clear"


@pytest.mark.parametrize("endpoint", [ANALYSIS, "/api/v1/geocode/"])
def test_options_no_provider_call(api: Harness, endpoint: str) -> None:
    response = api.client.options(endpoint)
    assert response.status_code == 405
    schema_check("ErrorResponse", response.json())
    assert api.router.calls == 0


def test_request_metrics_are_isolated() -> None:
    from fractions import Fraction

    first, second = Deadline(35, time.monotonic), Deadline(35, time.monotonic)
    first.record_call("routing")
    first.record_call("weather")
    first.record_reservation(Fraction(3, 2))
    second.record_call("geocoding")
    assert first.metrics() == ({"routing": 1, "geocoding": 0, "weather": 1}, Fraction(3, 2))
    assert second.metrics() == ({"routing": 0, "geocoding": 1, "weather": 0}, Fraction(0))


@pytest.mark.parametrize(
    "query,status",
    [("  abc  ", 200), ("x" * 200, 200), ("x" * 201, 400), ("", 400), ("a\nbc", 400)],
)
def test_geocoding_query_limits(api: Harness, query: str, status: int) -> None:
    response = api.client.get("/api/v1/geocode/", {"q": query})
    assert response.status_code == status
    schema_check("GeocodeResponse" if status == 200 else "ErrorResponse", response.json())


def test_geocoding_empty_results(api: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    from providers.contracts import PENDING_ATTRIBUTION, GeocodeResult

    def empty(query: str, *, deadline: Deadline) -> GeocodeResult:
        return GeocodeResult((), PENDING_ATTRIBUTION)

    monkeypatch.setattr(api.service.geocoder, "geocode", empty)
    response = api.client.get("/api/v1/geocode/?q=Synthetic")
    assert response.status_code == 200 and response.json()["candidates"] == []
    schema_check("GeocodeResponse", response.json())


def test_lazy_wiring_uses_shared_ledger_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.routing import factory
    from providers.tomtom import TomTomRouter
    from providers.weather import OpenMeteoWeather

    original = factory.get_service

    class NoNetworkClient:
        def get(self, *args: Any, **kwargs: Any) -> Any:
            pytest.fail("composition made an upstream request")

        def close(self) -> None:
            pass

    monkeypatch.setattr(factory, "HttpxClient", NoNetworkClient)
    # Unwrap the cache: this check creates configuration, never provider responses.
    service = original.__wrapped__()
    assert isinstance(service.weather, OpenMeteoWeather)
    assert isinstance(service.router, TomTomRouter)
    try:
        assert service.weather.transport.ledger is service.ledger
        assert service.router._transport.config.routing_read_seconds <= 25
        assert service.max_coordinates == 200
    finally:
        service.close()
        service.weather.close()
        service.router._transport.close()


def test_cors_preflight_no_provider_work(api: Harness) -> None:
    with override_settings(CORS_ALLOWED_ORIGINS=["http://localhost:5173"]):
        response = api.client.options(
            ANALYSIS,
            HTTP_ORIGIN="http://localhost:5173",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type",
        )
    assert response.status_code == 200 and response.content == b""
    assert response["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert api.router.calls == api.weather.calls == 0
