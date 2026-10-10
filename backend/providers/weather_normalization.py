"""Pure Open-Meteo hourly normalization; incomplete hours never become complete samples."""

import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Context, Decimal, localcontext
from fractions import Fraction
from types import MappingProxyType
from typing import cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from domain.route_types import Coordinate, RouteError, exact_number

from providers.contracts import (
    HourlyWeather,
    Unavailable,
    UnavailableReason,
    WeatherProvenance,
    WeatherSeries,
    WeatherSource,
    WeatherValues,
    WeatherWindow,
)
from providers.errors import ErrorCode, ProviderError
from providers.forecast import utc_epoch
from providers.transport import MAX_BODY_BYTES, HTTPResponse

REQUIRED_VARIABLES = ("wind_speed_10m", "rain", "showers", "snowfall")
GUST_VARIABLE = "wind_gusts_10m"
WIND_FACTORS = MappingProxyType(
    {
        "mph": Fraction(1),
        "mp/h": Fraction(1),
        "km/h": 1 / Fraction("1.609344"),
        "m/s": Fraction("2.2369362921"),
        "kn": Fraction("1.150779448"),
        "knots": Fraction("1.150779448"),
    }
)
DEPTH_FACTORS = MappingProxyType(
    {"inch": Fraction(1), "in": Fraction(1), "mm": 1 / Fraction("25.4"), "cm": 1 / Fraction("2.54")}
)
CONVERSION_PRECISION = 60


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ProviderError(ErrorCode.MALFORMED_PROVIDER_RESPONSE)
    return cast(dict[str, object], value)


def weather_json(response: HTTPResponse) -> dict[str, object] | list[object]:
    """Multi-coordinate successes are lists; normalize errors elsewhere without bodies."""
    value: object = None
    failed = False
    try:
        if len(response.body) > MAX_BODY_BYTES:
            failed = True
        else:
            value = json.loads(response.body, parse_float=Decimal, parse_constant=lambda _: None)
    except (ValueError, RecursionError, UnicodeError):
        failed = True
    media = response.content_type.split(";", 1)[0].strip().lower()
    if (
        failed
        or not isinstance(value, (dict, list))
        or not (media == "application/json" or media.endswith("+json"))
    ):
        raise ProviderError(ErrorCode.MALFORMED_PROVIDER_RESPONSE) from None
    return cast(dict[str, object] | list[object], value)


def _raw_number(value: object) -> Fraction | None:
    try:
        number = exact_number(cast(Decimal, value), "weather observation")
        return number if number >= 0 else None
    except (RouteError, ValueError, TypeError, OverflowError):
        return None


def _decimal(value: Fraction) -> Decimal:
    # Source fractions retain exact conversions. Domain-compatible Decimal output
    # uses a fixed precision independent of ambient context, no epsilon or rounding
    # to risk bands. Sixty digits exceed provider measurement precision.
    with localcontext(Context(prec=CONVERSION_PRECISION)):
        return Decimal(value.numerator) / Decimal(value.denominator)


def _converted(
    value: Fraction | None, unit: str | None, factors: Mapping[str, Fraction]
) -> Fraction | None:
    return None if value is None or unit not in factors else value * factors[cast(str, unit)]


def normalize_series(
    value: object,
    coordinate: Coordinate,
    window: WeatherWindow,
    *,
    model: str,
    fetched_at: datetime,
    gusts: bool = False,
) -> WeatherSeries:
    """Validate each field's metadata and arrays; retain known D08 evidence on unavailable rows."""
    obj = _object(value)
    hourly = _object(obj.get("hourly"))
    metadata = _object(obj.get("hourly_units"))
    times = hourly.get("time")
    if (
        not isinstance(times, list)
        or metadata.get("time") != "unixtime"
        or any(type(t) is not int or t % 3600 for t in times)
        or times != sorted(set(times))
    ):
        raise ProviderError(ErrorCode.MALFORMED_PROVIDER_RESPONSE)
    timestamps = cast(list[int], times)
    positions = {t: i for i, t in enumerate(timestamps)}
    names = (*REQUIRED_VARIABLES, GUST_VARIABLE) if gusts else REQUIRED_VARIABLES
    units = {
        name: unit if isinstance(unit, str) else None
        for name in names
        for unit in (metadata.get(name),)
    }
    arrays: dict[str, list[object]] = {}
    missing_fields = []
    for name in names:
        array = hourly.get(name)
        factors = WIND_FACTORS if name in {"wind_speed_10m", GUST_VARIABLE} else DEPTH_FACTORS
        aligned = isinstance(array, list) and len(array) == len(timestamps)
        if aligned:
            arrays[name] = cast(list[object], array)
        if (
            not isinstance(array, list)
            or len(array) != len(timestamps)
            or units[name] not in factors
        ):
            if name in REQUIRED_VARIABLES:
                missing_fields.append(name)
    rows: dict[int, HourlyWeather | Unavailable] = {}
    provenance = WeatherProvenance("Open-Meteo", model, utc_epoch(fetched_at))
    for stamp in window.hours:
        if stamp not in positions:
            reason = (
                UnavailableReason.OUT_OF_HORIZON
                if not timestamps or stamp < timestamps[0] or stamp > timestamps[-1]
                else UnavailableReason.MISSING_HOUR
            )
            rows[stamp] = Unavailable(reason)
            continue
        i = positions[stamp]
        raw = {name: _raw_number(arrays[name][i]) if name in arrays else None for name in names}
        wind = _converted(raw["wind_speed_10m"], units["wind_speed_10m"], WIND_FACTORS)
        rain, showers = (_converted(raw[n], units[n], DEPTH_FACTORS) for n in ("rain", "showers"))
        snow = _converted(raw["snowfall"], units["snowfall"], DEPTH_FACTORS)
        liquid = rain + showers if rain is not None and showers is not None else None
        gust = (
            _converted(raw.get(GUST_VARIABLE), units.get(GUST_VARIABLE), WIND_FACTORS)
            if gusts
            else None
        )
        values = WeatherValues(
            *(_decimal(v) if v is not None else None for v in (wind, liquid, snow, gust))
        )
        source = WeatherSource(MappingProxyType(raw), MappingProxyType(units))
        invalid = tuple(n for n in REQUIRED_VARIABLES if raw[n] is None)
        if missing_fields or invalid:
            rows[stamp] = Unavailable(
                UnavailableReason.MISSING_FIELD
                if missing_fields
                else UnavailableReason.MISSING_HOUR,
                tuple(sorted(set(missing_fields) | set(invalid))),
                values,
                source,
            )
        else:
            rows[stamp] = HourlyWeather(stamp, values, source, provenance)
    timezone = obj.get("timezone")
    fallback = not isinstance(timezone, str)
    if not fallback:
        try:
            ZoneInfo(cast(str, timezone))
        except (ZoneInfoNotFoundError, ValueError):
            fallback = True
    zone = "UTC" if fallback else cast(str, timezone)
    offset = obj.get("utc_offset_seconds")
    if type(offset) is not int or not -86400 < offset < 86400:
        offset = 0
        fallback = True
        zone = "UTC"
    return WeatherSeries(
        coordinate,
        window,
        MappingProxyType(rows),
        provenance,
        zone,
        offset,
        fallback,
    )


def unavailable_series(
    coordinate: Coordinate,
    window: WeatherWindow,
    reason: UnavailableReason,
    *,
    model: str,
    fetched_at: datetime,
) -> WeatherSeries:
    return WeatherSeries(
        coordinate,
        window,
        MappingProxyType({t: Unavailable(reason) for t in window.hours}),
        WeatherProvenance("Open-Meteo", model, utc_epoch(fetched_at)),
        "UTC",
        0,
        True,
    )
