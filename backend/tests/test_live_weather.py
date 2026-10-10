"""OPTIONAL, once-only evidence: 50 + 100 coordinates, three HTTP calls, retries off.

Enable only ROUTESHIELD_LIVE_OPEN_METEO=1 and run this file alone. Normal pytest
skips it and blocks sockets. No responses, URLs or bulk coordinates are printed.
"""

import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from time import monotonic, perf_counter, sleep

import httpx
import pytest
from domain.route_types import Coordinate
from providers.contracts import HourlyWeather, WeatherWindow
from providers.deadline import Deadline
from providers.limiter import ProviderLimiter
from providers.quota import QuotaLedger
from providers.transport import HTTPResponse, HttpxClient
from providers.weather import OpenMeteoWeather
from providers.weather_cache import WeatherCache
from providers.weather_normalization import REQUIRED_VARIABLES
from providers.weather_transport import WeatherConfig, WeatherTransport


@pytest.mark.skipif(
    os.environ.get("ROUTESHIELD_LIVE_OPEN_METEO") != "1",
    reason="Requires explicit Open-Meteo live flag; three calls/150 coordinates.",
)
def test_open_meteo_live_smoke() -> None:
    native = HttpxClient()

    class CountingClient:
        def __init__(self) -> None:
            self.lock = Lock()
            self.calls = self.coordinates = 0
            self.statuses: list[int] = []
            self.seconds: list[float] = []

        def get(
            self,
            url: str,
            *,
            params: Sequence[tuple[str, str]],
            timeout: httpx.Timeout,
            deadline: Deadline,
        ) -> HTTPResponse:
            # This task's allowlist and once-only budget are narrower than adapter configuration.
            if url != "https://api.open-meteo.com/v1/forecast":
                raise AssertionError(
                    "The live smoke permits only the Open-Meteo forecast endpoint."
                )
            count = len(dict(params)["latitude"].split(","))
            with self.lock:
                if self.calls >= 3 or self.coordinates + count > 150:
                    raise AssertionError("The live smoke request/coordinate budget was exceeded.")
                self.calls += 1
                self.coordinates += count
            started = perf_counter()
            result = native.get(url, params=params, timeout=timeout, deadline=deadline)
            seconds = perf_counter() - started
            with self.lock:
                self.statuses.append(result.status)
                self.seconds.append(seconds)
            return result

    def clock() -> datetime:
        return datetime.now(UTC)

    client = CountingClient()
    ledger = QuotaLedger(clock)
    config = WeatherConfig(retries=0)  # No retry can silently consume the task budget.
    service = OpenMeteoWeather(
        WeatherTransport(client, clock, sleep, ProviderLimiter(monotonic, sleep), ledger, config),
        WeatherCache(clock),
    )
    start = (int(clock().timestamp()) // 3600 + 1) * 3600
    window = WeatherWindow(start, start + 48 * 3600)
    measurements: list[dict[str, object]] = []
    try:
        for count, latitude, longitude in [(50, 34.05, -118.25), (100, 39.74, -104.99)]:
            coordinates = tuple(
                Coordinate(longitude + (i % 10) * 0.02, latitude + (i // 10) * 0.02)
                for i in range(count)
            )
            started = perf_counter()
            result = service.fetch(coordinates, window, deadline=Deadline(35, monotonic))
            seconds = perf_counter() - started
            expected = count * len(window.hours)
            coverage = sum(
                isinstance(row, HourlyWeather) for s in result.series for row in s.hours.values()
            )
            nonnull = {
                name: sum(
                    row.source is not None and row.source.components.get(name) is not None
                    for s in result.series
                    for row in s.hours.values()
                )
                for name in REQUIRED_VARIABLES
            }
            failed = len(result.failed_indices)
            cache_hits = result.diagnostics.cache_hits
            measurements.append(
                {
                    "coordinates": count,
                    "http": result.diagnostics.upstream_attempts,
                    "seconds": round(seconds, 3),
                    "complete_hours": coverage,
                    "expected_hours": expected,
                    "nonnull": nonnull,
                    "failed_coordinates": failed,
                    "cache_hits": cache_hits,
                }
            )
            print(
                f"LIVE weather: coordinates={count}; HTTP={result.diagnostics.upstream_attempts}; "
                f"seconds={seconds:.3f}; complete_hours={coverage}/{expected}; "
                f"failed_coordinates={len(result.failed_indices)}; "
                f"cache_hits={result.diagnostics.cache_hits}"
            )
            print(f"LIVE non-null coverage: {nonnull}")
            assert failed == 0, "Live required-variable coverage was incomplete."
            assert coverage == expected and cache_hits == 0
        print(
            f"LIVE total: HTTP={client.calls}; coordinates={client.coordinates}; "
            f"statuses={sorted(client.statuses)}; request_seconds="
            f"{','.join(f'{n:.3f}' for n in client.seconds)}; quota_units={ledger.used}; retries=0"
        )
        assert client.calls == 3 and client.coordinates == 150 and client.statuses == [200] * 3
    finally:
        evidence = {
            "recording": "numeric counts, timestamps and latency only; no response data",
            "reference_utc": clock().isoformat(),
            "request_start_epoch": window.start_epoch,
            "request_end_epoch": window.end_epoch,
            "requests": client.calls,
            "coordinates": client.coordinates,
            "statuses": client.statuses,
            "request_seconds": [round(n, 3) for n in client.seconds],
            "operations": measurements,
            "retries": 0,
        }
        evidence_path = (
            Path(__file__).parent / "fixtures" / "providers" / "weather_live_smoke_measurement.json"
        )
        evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        service.close()
        native.close()
