"""D20/API-01..04: strict field errors and boundary values before quota/provider work."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from apps.routing.errors import APIError
from apps.routing.validation import parse_json, validate_trip

from tests.api_helpers import NOW, Harness, request_body
from tests.api_helpers import api as api


@pytest.mark.parametrize(
    "field,value,error_field",
    [
        ("load_weight_lb", True, "load_weight_lb"),
        ("load_weight_lb", -1, "load_weight_lb"),
        ("load_weight_lb", 100000.01, "load_weight_lb"),
        ("load_weight_lb", "30000", "load_weight_lb"),
        ("load_weight_lb", None, "load_weight_lb"),
        ("load_weight_lb", [], "load_weight_lb"),
        ("checkpoint_interval_miles", 10.0, "checkpoint_interval_miles"),
        ("checkpoint_interval_miles", True, "checkpoint_interval_miles"),
        ("checkpoint_interval_miles", 20, "checkpoint_interval_miles"),
        ("checkpoint_interval_miles", None, "checkpoint_interval_miles"),
        ("departure_timezone", "Mars/Planet", "departure_timezone"),
        ("departure_timezone", None, "departure_timezone"),
        ("departure_time", "2026-10-11T12:01:00", "departure_time"),
        ("departure_time", "2026-13-11T12:01:00+00:00", "departure_time"),
        ("departure_time", "2026-10-11T12:01:00+01:00", "departure_time"),
        ("origin", None, "origin"),
        ("destination", [], "destination"),
        ("unknown_field", "secret-value", "body"),
    ],
)
def test_invalid_top_level(api: Harness, field: str, value: object, error_field: str) -> None:
    status, data = api.post(request_body(**{field: value}))
    assert status == 400 and error_field in data["error"]["details"]
    assert api.router.calls == api.weather.calls == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("latitude", True),
        ("latitude", -90.01),
        ("latitude", 90.01),
        ("latitude", "0"),
        ("longitude", True),
        ("longitude", -180.01),
        ("longitude", 180.01),
        ("longitude", None),
        ("label", "x"),
        ("label", "x" * 201),
        ("label", None),
        ("label", "new\nline"),
        ("extra", "ignored"),
        ("candidate_id", True),
        ("provider", []),
        ("attribution", {"secret": "unsafe"}),
        ("attribution", {"confirmed": "true"}),
    ],
)
def test_invalid_place(api: Harness, field: str, value: object) -> None:
    body = request_body()
    body["origin"] = {"label": "Valid label", "latitude": 0, "longitude": 0, field: value}
    status, data = api.post(body)
    assert status == 400 and any(k.startswith("origin") for k in data["error"]["details"])
    assert api.router.calls == 0


@pytest.mark.parametrize(
    "value", ["Springfield", {"label": "Springfield"}, {"label": "Springfield", "latitude": 0}]
)
def test_location_selection_required(api: Harness, value: object) -> None:
    status, data = api.post(request_body(origin=value))
    assert status == 422 and data["error"]["code"] == "LOCATION_REQUIRES_SELECTION"
    assert data["error"]["details"]["origin"] == "COORDINATES_REQUIRED"
    assert api.router.calls == 0


def test_identical_endpoints(api: Harness) -> None:
    status, data = api.post(
        request_body(destination={"label": "Different label", "latitude": 0, "longitude": 0})
    )
    assert status == 400 and data["error"]["details"] == {"destination": "IDENTICAL_ENDPOINTS"}


@pytest.mark.parametrize("weight", [0, 100000, 30000.5, 40000.01])
def test_valid_boundary_weights(api: Harness, weight: float) -> None:
    status, data = api.post(request_body(load_weight_lb=weight))
    assert status == 200 and Decimal(data["trip"]["load_weight_lb"]) == Decimal(str(weight))


@pytest.mark.parametrize("interval", [10, 25, 50])
def test_valid_intervals(api: Harness, interval: int) -> None:
    assert (
        api.post(request_body(checkpoint_interval_miles=interval))[1]["trip"][
            "effective_interval_miles"
        ]
        == interval
    )


@pytest.mark.parametrize(
    "offset,valid",
    [
        (timedelta(minutes=-5), True),
        (timedelta(minutes=-5, microseconds=-1), False),
        (timedelta(days=7), True),
        (timedelta(days=7, microseconds=1), False),
    ],
)
def test_departure_limits(offset: timedelta, valid: bool) -> None:
    body = request_body(departure_time=(NOW + offset).isoformat())
    if valid:
        assert validate_trip(body, NOW).departure == NOW + offset
    else:
        with pytest.raises(APIError) as error:
            validate_trip(body, NOW)
        assert error.value.details == {"departure_time": "OUTSIDE_DEPARTURE_WINDOW"}


@pytest.mark.parametrize(
    "text,now,valid",
    [
        ("2026-03-08T02:30:00-05:00", datetime(2026, 3, 8, tzinfo=UTC), False),
        ("2026-11-01T01:30:00-04:00", datetime(2026, 11, 1, tzinfo=UTC), True),
        ("2026-11-01T01:30:00-05:00", datetime(2026, 11, 1, tzinfo=UTC), True),
        ("2026-11-01T01:30:00", datetime(2026, 11, 1, tzinfo=UTC), False),
        ("2026-11-01T01:30:00-06:00", datetime(2026, 11, 1, tzinfo=UTC), False),
    ],
)
def test_dst_wall_times(text: str, now: datetime, valid: bool) -> None:
    body = request_body(departure_time=text, departure_timezone="America/New_York")
    if valid:
        assert validate_trip(body, now).departure.utcoffset() == timedelta(0)
    else:
        with pytest.raises(APIError) as error:
            validate_trip(body, now)
        assert "departure_time" in error.value.details


@pytest.mark.parametrize("field", ["load_weight_lb", "origin.latitude", "origin.longitude"])
@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), float("-inf"), Decimal("NaN"), Decimal("Infinity")]
)
def test_nonfinite_domain_boundary(field: str, value: object) -> None:
    body = request_body()
    if field.startswith("origin"):
        body["origin"] = {
            "label": "Synthetic origin",
            "latitude": 0,
            "longitude": 0,
            field.split(".")[1]: value,
        }
    else:
        body[field] = value
    with pytest.raises(APIError) as error:
        validate_trip(body, NOW)
    assert error.value.details == {field: "NON_FINITE_VALUE"}


@pytest.mark.parametrize(
    "raw", ['{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}', '{"x":1,"x":2}', "{", "[]", "null"]
)
def test_invalid_json(api: Harness, raw: str) -> None:
    status, data = api.post(raw=raw)
    assert status == 400 and "body" in data["error"]["details"]


@pytest.mark.parametrize(
    "content_type", ["text/plain", "application/xml", "application/x-www-form-urlencoded"]
)
def test_json_only(api: Harness, content_type: str) -> None:
    status, data = api.post(content_type=content_type)
    assert status == 415 and data["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_size_checked_before_parse(api: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(_: bytes) -> object:
        pytest.fail("oversized request reached JSON parser")

    monkeypatch.setattr("apps.routing.views.parse_json", forbidden)
    status, data = api.post(raw="{" + "x" * 16384)
    assert status == 413 and data["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert api.router.calls == 0


@pytest.mark.parametrize("size,valid", [(16384, True), (16385, False)])
def test_json_size_exact_boundary(size: int, valid: bool) -> None:
    raw = json.dumps({"x": "a" * (size - 8)}, separators=(",", ":")).encode()
    assert len(raw) == size
    if valid:
        assert isinstance(parse_json(raw), dict)
    else:
        with pytest.raises(APIError) as error:
            parse_json(raw)
        assert error.value.code == "PAYLOAD_TOO_LARGE"
