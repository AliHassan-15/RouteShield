"""API boundary checks; decimal parsing precedes pure domain computations."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from unicodedata import category
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from domain.route_types import Coordinate

from apps.routing.errors import APIError

MAX_BODY_BYTES = 16 * 1024
SCENARIOS = (
    "all_clear",
    "high_wind_corridor",
    "winter_storm",
    "heavy_rain_front",
    "blocked_trip",
    "tie_break",
)


@dataclass(frozen=True)
class Place:
    label: str
    coordinate: Coordinate
    candidate_id: str | None = None
    provider: str | None = None
    attribution: Mapping[str, object] | None = None


@dataclass(frozen=True)
class Trip:
    origin: Place
    destination: Place
    departure: datetime
    timezone: str
    load: Decimal
    interval: int | None


def parse_json(body: bytes) -> object:
    """No rounding/coercion, nonstandard constants, duplicate keys or oversized parsing."""
    if len(body) > MAX_BODY_BYTES:
        raise APIError("PAYLOAD_TOO_LARGE")

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def constant(_: str) -> object:
        raise ValueError("nonstandard number")

    try:
        return cast(
            object,
            json.loads(body, parse_float=Decimal, parse_constant=constant, object_pairs_hook=pairs),
        )
    except (ValueError, UnicodeError, RecursionError):
        raise APIError("VALIDATION_ERROR", {"body": "INVALID_JSON"}) from None


def _object(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise APIError("VALIDATION_ERROR", {field: "EXPECTED_OBJECT"})
    return cast(dict[str, object], value)


def _unknown(value: Mapping[str, object], allowed: set[str], field: str) -> None:
    # Do not echo arbitrary property names (they may contain secrets/URLs).
    if set(value) - allowed:
        raise APIError("VALIDATION_ERROR", {field: "UNKNOWN_FIELDS"})


def _text(value: object, field: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise APIError("VALIDATION_ERROR", {field: "INVALID_LENGTH_OR_TYPE"})
    if any(category(c) in {"Cc", "Cs"} for c in value):
        raise APIError("VALIDATION_ERROR", {field: "CONTROL_CHARACTER"})
    return value.strip()


def _number(value: object, field: str, low: int, high: int) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise APIError("VALIDATION_ERROR", {field: "EXPECTED_NUMBER"})
    number = Decimal(str(value))
    if not number.is_finite():
        raise APIError("VALIDATION_ERROR", {field: "NON_FINITE_VALUE"})
    if not low <= number <= high:
        raise APIError("VALIDATION_ERROR", {field: "OUT_OF_RANGE"})
    return number


def _place(value: object, field: str) -> Place:
    if isinstance(value, str):
        raise APIError("LOCATION_REQUIRES_SELECTION", {field: "COORDINATES_REQUIRED"})
    obj = _object(value, field)
    _unknown(
        obj, {"label", "latitude", "longitude", "candidate_id", "provider", "attribution"}, field
    )
    if "latitude" not in obj or "longitude" not in obj:
        raise APIError("LOCATION_REQUIRES_SELECTION", {field: "COORDINATES_REQUIRED"})
    label = _text(obj.get("label"), field + ".label", 2, 200)
    lat = _number(obj.get("latitude"), field + ".latitude", -90, 90)
    lon = _number(obj.get("longitude"), field + ".longitude", -180, 180)
    candidate = (
        None
        if obj.get("candidate_id") is None
        else _text(obj["candidate_id"], field + ".candidate_id", 1, 200)
    )
    provider = (
        None if obj.get("provider") is None else _text(obj["provider"], field + ".provider", 1, 100)
    )
    attribution = None
    if obj.get("attribution") is not None:
        attribution = _object(obj["attribution"], field + ".attribution")
        _unknown(
            attribution,
            {"provider", "text", "confirmed", "source_url", "licence_url"},
            field + ".attribution",
        )
        for key, item in attribution.items():
            if key == "confirmed":
                if type(item) is not bool:
                    raise APIError("VALIDATION_ERROR", {field + ".attribution": "INVALID_TYPE"})
            elif item is not None:
                _text(item, field + ".attribution", 1, 1000)
    return Place(label, Coordinate(float(lon), float(lat)), candidate, provider, attribution)


def validate_trip(value: object, now: datetime) -> Trip:
    """Require a real zoned instant and selected coordinates, before any provider work."""
    obj = _object(value, "body")
    _unknown(
        obj,
        {
            "origin",
            "destination",
            "departure_time",
            "departure_timezone",
            "load_weight_lb",
            "checkpoint_interval_miles",
            "simulation_scenario",
        },
        "body",
    )
    scenario = obj.get("simulation_scenario")
    if scenario is not None:
        if not isinstance(scenario, str) or scenario not in SCENARIOS:
            raise APIError("INVALID_SCENARIO", {"simulation_scenario": "INVALID_SCENARIO"})
        raise APIError("SIMULATION_DISABLED", {"simulation_scenario": "DISABLED"})
    origin, destination = (
        _place(obj.get("origin"), "origin"),
        _place(obj.get("destination"), "destination"),
    )
    if origin.coordinate == destination.coordinate:
        raise APIError("VALIDATION_ERROR", {"destination": "IDENTICAL_ENDPOINTS"})
    load = _number(obj.get("load_weight_lb"), "load_weight_lb", 0, 100000)
    interval = obj.get("checkpoint_interval_miles")
    if "checkpoint_interval_miles" in obj and (
        type(interval) is not int or interval not in (10, 25, 50)
    ):
        raise APIError("VALIDATION_ERROR", {"checkpoint_interval_miles": "INVALID_INTERVAL"})
    zone_name = _text(obj.get("departure_timezone"), "departure_timezone", 1, 100)
    try:
        zone = ZoneInfo(zone_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise APIError("VALIDATION_ERROR", {"departure_timezone": "INVALID_IANA_ZONE"}) from None
    text = obj.get("departure_time")
    if not isinstance(text, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})", text
    ):
        raise APIError("VALIDATION_ERROR", {"departure_time": "OFFSET_REQUIRED"})
    try:
        departure = datetime.fromisoformat(text)
        utc = departure.astimezone(UTC)
        local = utc.astimezone(zone)
    except (ValueError, OverflowError):
        raise APIError("VALIDATION_ERROR", {"departure_time": "INVALID_DATETIME"}) from None
    if local.replace(tzinfo=None) != departure.replace(tzinfo=None) or (
        local.utcoffset() != departure.utcoffset()
    ):
        raise APIError(
            "VALIDATION_ERROR", {"departure_time": "ZONE_OFFSET_MISMATCH_OR_NONEXISTENT"}
        )
    if not now - timedelta(minutes=5) <= utc <= now + timedelta(days=7):
        raise APIError("VALIDATION_ERROR", {"departure_time": "OUTSIDE_DEPARTURE_WINDOW"})
    return Trip(origin, destination, utc, zone_name, load, cast(int | None, interval))


def validate_query(params: Mapping[str, object]) -> str:
    """An autocomplete lookup returns choices; it never selects one for the driver."""
    _unknown(params, {"q"}, "query")
    return _text(params.get("q"), "q", 3, 200)
