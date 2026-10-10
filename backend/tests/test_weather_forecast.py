"""WX-02/03/04/05/07, HEAT-03/05, TIME-01: pure time selection and display."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from types import MappingProxyType

import pytest
from providers.contracts import HourlyWeather, Unavailable, UnavailableReason, WeatherWindow
from providers.errors import ProviderError
from providers.forecast import (
    forecast_local_time,
    forecast_window,
    lookup_forecast,
    series_age,
    series_is_stale,
    utc_epoch,
    validate_window,
)

from tests.provider_helpers import NOW
from tests.weather_helpers import START, WINDOW, hourly, instant, payload, series


@pytest.mark.parametrize(
    "offset,row",
    [(1200, 3600), (3600, 3600), (3601, 7200), (Fraction(3600000001, 1000000), 7200), (0, 0)],
)
def test_enclosing_hour(offset: Fraction, row: int) -> None:
    result = lookup_forecast(series(payload()), instant(START + offset), now=NOW)
    assert result.eta_epoch == START + offset
    assert result.forecast_epoch == START + row
    assert isinstance(result.result, HourlyWeather)
    assert result.result.forecast_epoch == result.forecast_epoch


@pytest.mark.parametrize(
    "offset,reason",
    [
        (-1, UnavailableReason.OUT_OF_HORIZON),
        (49 * 3600, UnavailableReason.OUT_OF_HORIZON),
        (48 * 3600 + 1, UnavailableReason.OUT_OF_HORIZON),
    ],
)
def test_lookup_never_uses_nearest_endpoint(offset: int, reason: UnavailableReason) -> None:
    result = lookup_forecast(
        series(payload()), instant(START + offset), now=NOW - timedelta(days=1)
    )
    assert isinstance(result.result, Unavailable) and result.result.reason is reason


def test_last_hour_missing_interior_and_past_time() -> None:
    doc = payload()
    row = series(doc)
    assert isinstance(
        lookup_forecast(row, instant(WINDOW.end_epoch), now=NOW).result, HourlyWeather
    )
    altered = replace(
        row, hours=MappingProxyType({t: v for t, v in row.hours.items() if t != START + 3600})
    )
    missing = lookup_forecast(altered, instant(START + 1200), now=NOW).result
    assert isinstance(missing, Unavailable) and missing.reason is UnavailableReason.MISSING_HOUR
    hourly(doc)["showers"] = [None] * len(WINDOW.hours)
    unknown = lookup_forecast(series(doc), instant(START + 1200), now=NOW).result
    assert isinstance(unknown, Unavailable) and unknown.reason is UnavailableReason.MISSING_HOUR
    past = lookup_forecast(row, NOW - timedelta(seconds=1), now=NOW).result
    assert isinstance(past, Unavailable) and past.reason is UnavailableReason.PAST_TIME


@pytest.mark.parametrize("travel_hours,expected_hours", [(12, 49), (48, 49), (70, 71)])
def test_window_floor_departure_ceil_longest_eta(travel_hours: int, expected_hours: int) -> None:
    departure = NOW + timedelta(minutes=20)
    window = forecast_window(departure, departure + timedelta(hours=travel_hours))
    assert window.start_epoch == START
    assert window.end_epoch == START + expected_hours * 3600
    assert len(window.hours) == expected_hours + 1


@pytest.mark.parametrize(
    "bad",
    [
        WeatherWindow(1, 3600),
        WeatherWindow(3600, 0),
        WeatherWindow(-3600, 0),
        WeatherWindow(0, True),
        WeatherWindow(0, 3601),
    ],
)
def test_invalid_window_rejected(bad: WeatherWindow) -> None:
    with pytest.raises(ProviderError):
        validate_window(bad)


def test_naive_or_backwards_times_are_invalid() -> None:
    with pytest.raises(ProviderError):
        utc_epoch(NOW.replace(tzinfo=None))
    with pytest.raises(ProviderError):
        forecast_window(NOW, NOW - timedelta(seconds=1))


def test_dst_repeat_uses_utc_rows_and_iana_display() -> None:
    first = datetime(2026, 11, 1, 5, tzinfo=UTC)
    window = WeatherWindow(int(first.timestamp()), int(first.timestamp()) + 3600)
    doc = payload(window)
    doc.update(timezone="America/New_York", utc_offset_seconds=-14400)
    result = series(doc, window)
    one = lookup_forecast(result, first, now=first)
    two = lookup_forecast(result, first + timedelta(hours=1), now=first)
    a = forecast_local_time(result, one.forecast_epoch)
    b = forecast_local_time(result, two.forecast_epoch)
    assert a.hour == b.hour == 1 and a.fold == 0 and b.fold == 1
    assert a.utcoffset() == timedelta(hours=-4) and b.utcoffset() == timedelta(hours=-5)
    assert one.forecast_epoch != two.forecast_epoch


@pytest.mark.parametrize(
    "zone,offset", [(None, 0), ("invalid/IANA", 0), ("UTC", None), ("UTC", True), ("UTC", 86400)]
)
def test_invalid_display_metadata_is_explicit_utc_fallback(zone: object, offset: object) -> None:
    doc = payload()
    doc.update(timezone=zone, utc_offset_seconds=offset)
    result = series(doc)
    assert result.timezone == "UTC" and result.timezone_fallback
    assert result.complete


def test_age_and_staleness_preserve_old_payload_diagnostics() -> None:
    result = series(payload())
    assert series_age(result, NOW + timedelta(seconds=899, microseconds=999999)) < 900
    assert not series_is_stale(result, NOW + timedelta(seconds=899))
    assert series_is_stale(result, NOW + timedelta(seconds=900))
    assert series_age(result, NOW - timedelta(seconds=1)) == 0
