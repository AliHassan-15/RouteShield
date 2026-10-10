"""WX-01/02/03/04/07/08/09/11/12/13, HEAT-05: synthetic normalization evidence."""

from dataclasses import FrozenInstanceError
from decimal import ROUND_DOWN, ROUND_UP, Decimal, localcontext
from fractions import Fraction
from itertools import combinations
from typing import cast

import pytest
from providers.contracts import HourlyWeather, Unavailable, UnavailableReason
from providers.errors import ErrorCode, ProviderError
from providers.transport import HTTPResponse
from providers.weather_normalization import weather_json

from tests.provider_helpers import response
from tests.weather_helpers import START, VARIABLES, WINDOW, hourly, payload, series, units


@pytest.mark.parametrize(
    "field,unit,value,expected",
    [
        ("wind_speed_10m", "mph", 55, "55"),
        ("wind_speed_10m", "mp/h", 55, "55"),
        ("wind_speed_10m", "km/h", 88.51392, "55"),
        ("wind_speed_10m", "m/s", 10, "22.369362921"),
        ("wind_speed_10m", "kn", 10, "11.50779448"),
        ("wind_speed_10m", "knots", 10, "11.50779448"),
        ("rain", "mm", 25.4, "1.15"),
        ("rain", "cm", 2.54, "1.15"),
        ("rain", "inch", 1, "1.15"),
        ("rain", "in", 1, "1.15"),
        ("showers", "mm", 25.4, "1.1"),
        ("showers", "cm", 2.54, "1.1"),
        ("snowfall", "mm", 25.4, "1"),
        ("snowfall", "cm", 2.54, "1"),
        ("snowfall", "inch", 3, "3"),
        ("snowfall", "in", 3, "3"),
    ],
)
def test_each_field_unit_conversion(field: str, unit: str, value: float, expected: str) -> None:
    doc = payload()
    units(doc)[field] = unit
    hourly(doc)[field] = [value] * len(WINDOW.hours)
    row = series(doc).hours[START]
    assert isinstance(row, HourlyWeather)
    observed = (
        row.values.wind_mph
        if field == "wind_speed_10m"
        else row.values.snow_in_hr
        if field == "snowfall"
        else row.values.rain_in_hr
    )
    assert observed == Decimal(expected)
    assert row.source.units[field] == unit
    assert row.source.components[field] == Fraction(str(value))
    assert row.source.hourly_average_rates
    assert row.provenance.model == "best_match"


def test_exact_liquid_addition_and_independent_decimal_context() -> None:
    doc = payload()
    with localcontext() as context:
        context.prec = 2
        first = series(doc)
    with localcontext() as context:
        context.prec = 50
        second = series(doc)
    assert first == second
    row = first.hours[START]
    assert isinstance(row, HourlyWeather)
    assert row.values.rain_in_hr == Decimal("0.25")
    assert row.values.snow_in_hr == Decimal("0.5")
    assert row.values.gust_mph is None


def test_nonterminating_conversion_ignores_ambient_rounding_mode() -> None:
    doc = payload(wind=1)
    units(doc)["wind_speed_10m"] = "km/h"
    with localcontext() as context:
        context.prec, context.rounding = 2, ROUND_DOWN
        first = series(doc)
    with localcontext() as context:
        context.prec, context.rounding = 90, ROUND_UP
        second = series(doc)
    assert first == second


def test_irrelevant_precipitation_and_snow_water_equivalent_are_never_used() -> None:
    doc = payload()
    hourly(doc)["precipitation"] = [100] * len(WINDOW.hours)
    hourly(doc)["snowfall_water_equivalent"] = [100] * len(WINDOW.hours)
    original = series(doc)
    del hourly(doc)["showers"]
    missing = series(doc)
    assert original.complete and not missing.complete
    row = missing.hours[START]
    assert isinstance(row, Unavailable) and row.known_values.rain_in_hr is None
    assert row.known_values.snow_in_hr == Decimal("0.5")


@pytest.mark.parametrize("field", VARIABLES)
@pytest.mark.parametrize("unit", [None, "unrecognized", 1, ""])
def test_missing_or_unknown_units_are_field_unavailable(field: str, unit: object) -> None:
    doc = payload(wind=55)
    units(doc)[field] = unit
    row = series(doc).hours[START]
    assert isinstance(row, Unavailable)
    assert row.reason is UnavailableReason.MISSING_FIELD
    assert field in row.missing_fields
    assert row.source is not None and row.source.components[field] is not None
    result = row.known_values
    assert (
        result.wind_mph
        if field == "wind_speed_10m"
        else result.snow_in_hr
        if field == "snowfall"
        else result.rain_in_hr
    ) is None


@pytest.mark.parametrize("field", VARIABLES)
@pytest.mark.parametrize(
    "bad",
    [
        None,
        -1,
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
        False,
        "1",
        Decimal("NaN"),
        Decimal("Infinity"),
    ],
)
def test_invalid_values_never_become_calm(field: str, bad: object) -> None:
    doc = payload(wind=55)
    hourly(doc)[field] = [bad] * len(WINDOW.hours)
    normalized = series(doc)
    assert not normalized.complete
    row = normalized.hours[START]
    assert isinstance(row, Unavailable)
    assert row.reason is UnavailableReason.MISSING_HOUR
    result = row.known_values
    assert (
        result.wind_mph
        if field == "wind_speed_10m"
        else result.snow_in_hr
        if field == "snowfall"
        else result.rain_in_hr
    ) is None


@pytest.mark.parametrize("field", VARIABLES)
@pytest.mark.parametrize("kind", ["absent", "null", "short", "long", "scalar"])
def test_array_alignment_required(field: str, kind: str) -> None:
    doc = payload()
    array = hourly(doc)
    if kind == "absent":
        del array[field]
    else:
        array[field] = {"null": None, "short": [0], "long": [0] * 100, "scalar": 0}[kind]
    row = series(doc).hours[START]
    assert isinstance(row, Unavailable)
    assert row.reason is UnavailableReason.MISSING_FIELD
    assert field in row.missing_fields


@pytest.mark.parametrize(
    "missing", [subset for n in range(1, 5) for subset in combinations(VARIABLES, n)]
)
@pytest.mark.parametrize("mode", ["null", "absent", "bad_unit"])
def test_property_missing_any_required_input_never_yields_complete_sample(
    missing: tuple[str, ...], mode: str
) -> None:
    doc = payload(wind=55)
    for field in missing:
        if mode == "absent":
            del hourly(doc)[field]
        elif mode == "null":
            hourly(doc)[field] = [None] * len(WINDOW.hours)
        else:
            units(doc)[field] = "unknown"
    result = series(doc)
    assert all(isinstance(row, Unavailable) for row in result.hours.values())
    assert not result.complete
    # D08 retains known block evidence; it never labels this an HourlyWeather sample.
    first = result.hours[START]
    assert isinstance(first, Unavailable)
    if "wind_speed_10m" not in missing:
        assert first.known_values.wind_mph == 55
    if "rain" in missing or "showers" in missing:
        assert first.known_values.rain_in_hr is None


def test_null_tail_timestamps_do_not_prove_coverage() -> None:
    doc = payload()
    for field in VARIABLES:
        array = cast(list[object], hourly(doc)[field])
        array[-2:] = [None, None]
    result = series(doc)
    assert isinstance(result.hours[WINDOW.end_epoch - 7200], HourlyWeather)
    assert isinstance(result.hours[WINDOW.end_epoch - 3600], Unavailable)
    assert isinstance(result.hours[WINDOW.end_epoch], Unavailable)
    assert not result.complete


@pytest.mark.parametrize(
    "times", [[START, START], [START + 3600, START], [True], ["0"], [START + 1], [None]]
)
def test_malformed_timestamps_raise_safe_error(times: list[object]) -> None:
    doc = payload()
    hourly(doc)["time"] = times
    with pytest.raises(ProviderError) as caught:
        series(doc)
    assert caught.value.code is ErrorCode.MALFORMED_PROVIDER_RESPONSE


@pytest.mark.parametrize(
    "body,media",
    [
        (b"", "application/json"),
        (b"null", "application/json"),
        (b"123", "application/json"),
        (b"{", "application/json"),
        (b"<error/>", "application/xml"),
        (b"{}", "text/html"),
        (b"\xff", "application/json"),
    ],
)
def test_malformed_success_payloads_are_safe(body: bytes, media: str) -> None:
    with pytest.raises(ProviderError) as caught:
        weather_json(HTTPResponse(200, body, media))
    assert caught.value.code is ErrorCode.MALFORMED_PROVIDER_RESPONSE
    assert caught.value.__context__ is None


def test_json_epoch_decimals_optional_gust_and_immutability() -> None:
    doc = payload()
    parsed = weather_json(response(doc, content_type="Application/JSON; charset=utf-8"))
    result = series(parsed, gusts=True)
    row = result.hours[START]
    assert isinstance(row, HourlyWeather)
    assert row.values.gust_mph == 55 and row.values.wind_mph == 12
    with pytest.raises(FrozenInstanceError):
        row.values.wind_mph = Decimal(1)  # type: ignore[misc]
    with pytest.raises(TypeError):
        result.hours[START] = row  # type: ignore[index]
    with pytest.raises(TypeError):
        row.source.components["rain"] = Fraction(1)  # type: ignore[index]


def test_optional_bad_gust_does_not_make_required_weather_unavailable() -> None:
    doc = payload()
    hourly(doc)["wind_gusts_10m"] = [None] * len(WINDOW.hours)
    result = series(doc, gusts=True)
    assert result.complete
    row = result.hours[START]
    assert isinstance(row, HourlyWeather) and row.values.gust_mph is None
