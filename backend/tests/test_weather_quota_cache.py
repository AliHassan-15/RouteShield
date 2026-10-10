"""WX-06/10/13, API-08, QUOTA-01, TIME-01: exact reservations and weather-only TTL."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from fractions import Fraction

import pytest
from providers.contracts import HourlyWeather, UnavailableReason, WeatherWindow
from providers.errors import ProviderError
from providers.quota import QuotaLedger, quota_units
from providers.weather_cache import WeatherCache, WeatherCacheKey
from providers.weather_normalization import unavailable_series

from tests.provider_helpers import NOW, FakeTime
from tests.weather_helpers import POINT, START, VARIABLES, WINDOW, hourly, payload, series


def key() -> WeatherCacheKey:
    return WeatherCacheKey(
        "Open-Meteo",
        "best_match",
        "https://example.invalid/forecast",
        POINT,
        WINDOW,
        VARIABLES,
        ("mph", "inch", "UTC", "unixtime"),
    )


@pytest.mark.parametrize(
    "coords,variables,days,models,expected",
    [
        (300, 4, 3, 1, Fraction(300)),
        (1, 15, 14, 1, Fraction(3, 2)),
        (1, 15, 28, 1, Fraction(3)),
        (50, 4, 15, 1, Fraction(375, 7)),
        (2, 20, 28, 3, Fraction(24)),
        (1, 5, 2, 1, Fraction(1)),
    ],
)
def test_published_formula(
    coords: int, variables: int, days: int, models: int, expected: Fraction
) -> None:
    midnight = START - 12 * 3600
    window = WeatherWindow(midnight, midnight + days * 86400 - 3600)
    assert quota_units(coords, variables, window, models) == expected


def test_exact_limit_and_concurrent_fractional_reservations() -> None:
    ledger = QuotaLedger(FakeTime().utc, daily_limit=10, request_limit=10)
    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(lambda _: ledger.reserve(Fraction(1, 3)), range(100)))
    assert sum(r is not None for r in results) == 30
    assert ledger.used == 10 and ledger.reserve(Fraction(1, 1000)) is None


def test_pre_send_release_is_idempotent_but_sent_failure_keeps_charge() -> None:
    ledger = QuotaLedger(FakeTime().utc, daily_limit=2, request_limit=1)
    r = ledger.reserve(Fraction(1))
    assert r is not None
    ledger.release_before_send(r)
    ledger.release_before_send(r)
    assert ledger.used == 0 and not ledger.mark_sent(r)
    sent = ledger.reserve(Fraction(1))
    assert sent is not None and ledger.mark_sent(sent)
    ledger.release_before_send(sent)
    assert ledger.used == 1
    assert ledger.reserve(Fraction(2)) is None


def test_utc_rollover_and_restart_reset_without_negative_release() -> None:
    time = FakeTime()
    ledger = QuotaLedger(time.utc, daily_limit=1, request_limit=1)
    yesterday = ledger.reserve(Fraction(1))
    assert yesterday is not None
    time.seconds = 12 * 3600
    today = ledger.reserve(Fraction(1))
    assert today is not None and ledger.used == 1
    ledger.release_before_send(yesterday)
    assert ledger.used == 1
    assert QuotaLedger(time.utc).used == 0


def test_pending_reservation_crossing_midnight_rechecks_current_day_limit() -> None:
    time = FakeTime()
    ledger = QuotaLedger(time.utc, daily_limit=1, request_limit=1)
    old = ledger.reserve(Fraction(1))
    assert old is not None
    time.seconds = 12 * 3600
    assert ledger.mark_sent(old) and ledger.used == 1
    time.seconds += 86400
    queued = ledger.reserve(Fraction(1))
    assert queued is not None
    time.seconds += 86400
    current = ledger.reserve(Fraction(1))
    assert current is not None
    assert not ledger.mark_sent(queued) and ledger.used == 1


@pytest.mark.parametrize("units", [Fraction(0), Fraction(-1)])
def test_invalid_reservation(units: Fraction) -> None:
    with pytest.raises(ProviderError):
        QuotaLedger(FakeTime().utc).reserve(units)


def test_cache_hit_miss_age_and_exact_expiry() -> None:
    time = FakeTime()
    cache = WeatherCache(time.utc)
    assert cache.get(key()) is None
    original = series(payload())
    cache.put(key(), original)
    time.seconds = 899.999999
    found = cache.get(key())
    assert found is not None and found.provenance.cache_hit
    row = found.hours[START]
    assert isinstance(row, HourlyWeather) and row.provenance.cache_hit
    assert not original.provenance.cache_hit
    time.seconds = 900
    assert cache.get(key()) is None
    assert cache.hits == 1 and cache.misses == 2


@pytest.mark.parametrize(
    "changed", ["provider", "model", "source", "coordinate", "window", "variables", "units"]
)
def test_cache_key_is_exact(changed: str) -> None:
    from domain.route_types import Coordinate

    cache = WeatherCache(FakeTime().utc)
    cache.put(key(), series(payload()))
    options = {
        "provider": replace(key(), provider="other"),
        "model": replace(key(), model="gfs_seamless"),
        "source": replace(key(), source="https://other.invalid/forecast"),
        "coordinate": replace(key(), coordinate=Coordinate(-100.00001, 34)),
        "window": replace(key(), window=WeatherWindow(START, WINDOW.end_epoch + 3600)),
        "variables": replace(key(), variables=(*VARIABLES, "wind_gusts_10m")),
        "units": replace(key(), units=("km/h", "inch")),
    }
    assert cache.get(options[changed]) is None


@pytest.mark.parametrize("kind", ["null", "missing", "failure", "horizon"])
def test_failure_or_partial_never_cached(kind: str) -> None:
    doc = payload()
    if kind == "null":
        hourly(doc)["showers"] = [None] * len(WINDOW.hours)
        result = series(doc)
    elif kind == "missing":
        del hourly(doc)["rain"]
        result = series(doc)
    else:
        result = unavailable_series(
            POINT,
            WINDOW,
            UnavailableReason.PROVIDER_FAILURE
            if kind == "failure"
            else UnavailableReason.OUT_OF_HORIZON,
            model="best_match",
            fetched_at=NOW,
        )
    cache = WeatherCache(FakeTime().utc)
    cache.put(key(), result)
    assert cache.get(key()) is None


@pytest.mark.parametrize("ttl", [0, 901, True])
def test_invalid_cache_ttl(ttl: int) -> None:
    with pytest.raises(ProviderError):
        WeatherCache(FakeTime().utc, ttl_seconds=ttl)


def test_cache_entry_bound_evicts_oldest() -> None:
    cache = WeatherCache(FakeTime().utc, max_entries=1)
    cache.put(key(), series(payload()))
    second = replace(key(), model="gfs_seamless")
    cache.put(second, series(payload()))
    assert cache.get(key()) is None and cache.get(second) is not None
