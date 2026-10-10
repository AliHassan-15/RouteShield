"""Pure UTC windows, safe enclosing-hour lookup, age and local display helpers."""

from datetime import UTC, datetime
from fractions import Fraction
from zoneinfo import ZoneInfo

from providers.contracts import (
    ForecastLookup,
    HourlyWeather,
    Unavailable,
    UnavailableReason,
    WeatherSeries,
    WeatherWindow,
)
from providers.errors import ErrorCode, ProviderError

HOUR_SECONDS = 3600
FORECAST_SLIDER_SECONDS = 48 * HOUR_SECONDS
WEATHER_TTL_SECONDS = 900
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def utc_epoch(instant: datetime) -> Fraction:
    """Retain microseconds exactly without binary timestamp rounding."""
    if not isinstance(instant, datetime) or instant.tzinfo is None or instant.utcoffset() is None:
        raise ProviderError(ErrorCode.INVALID_REQUEST)
    delta = instant.astimezone(UTC) - EPOCH
    return Fraction(delta.days * 86400 + delta.seconds) + Fraction(delta.microseconds, 1000000)


def enclosing_hour(epoch: Fraction) -> int:
    """Row t owns (t−3600,t]; exact hour stays on that row."""
    return -int((-epoch) // HOUR_SECONDS) * HOUR_SECONDS


def forecast_window(departure: datetime, latest_eta: datetime) -> WeatherWindow:
    """Floor departure; ceil the later of departure+48h and final ETA."""
    start, latest = utc_epoch(departure), utc_epoch(latest_eta)
    if latest < start:
        raise ProviderError(ErrorCode.INVALID_REQUEST)
    return WeatherWindow(
        int(start // HOUR_SECONDS) * HOUR_SECONDS,
        enclosing_hour(max(start + FORECAST_SLIDER_SECONDS, latest)),
    )


def validate_window(window: WeatherWindow) -> None:
    """Bound malformed requests before any allocation, quota reservation or network."""
    if (
        not isinstance(window, WeatherWindow)
        or type(window.start_epoch) is not int
        or type(window.end_epoch) is not int
        or window.start_epoch < 0
        or window.end_epoch < window.start_epoch
        or window.start_epoch % HOUR_SECONDS
        or window.end_epoch % HOUR_SECONDS
    ):
        raise ProviderError(ErrorCode.INVALID_REQUEST)


def lookup_forecast(series: WeatherSeries, eta: datetime, *, now: datetime) -> ForecastLookup:
    """No nearest endpoint, extrapolation, category/accumulation interpolation or calm fallback."""
    epoch = utc_epoch(eta)
    row = enclosing_hour(epoch)
    value: HourlyWeather | Unavailable
    if epoch < utc_epoch(now):
        value = Unavailable(UnavailableReason.PAST_TIME)
    elif epoch < series.window.start_epoch or epoch > series.window.end_epoch:
        value = Unavailable(UnavailableReason.OUT_OF_HORIZON)
    else:
        value = series.hours.get(row, Unavailable(UnavailableReason.MISSING_HOUR))
    return ForecastLookup(epoch, row, value)


def series_age(series: WeatherSeries, now: datetime) -> Fraction:
    """Payload age remains observable even after removal from the cache."""
    return max(Fraction(0), utc_epoch(now) - series.provenance.fetched_at)


def series_is_stale(series: WeatherSeries, now: datetime) -> bool:
    return series_age(series, now) >= WEATHER_TTL_SECONDS


def forecast_local_time(series: WeatherSeries, forecast_epoch: int) -> datetime:
    """Use IANA rules for DST; the provider's fixed offset is diagnostic only."""
    return datetime.fromtimestamp(forecast_epoch, UTC).astimezone(ZoneInfo(series.timezone))
