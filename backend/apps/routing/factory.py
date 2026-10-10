"""Lazy process composition: no request/result retention and no network on startup."""

import atexit
import time
from datetime import UTC, datetime
from functools import lru_cache
from typing import cast
from uuid import uuid4

from django.conf import settings
from providers.deadline import Deadline
from providers.limiter import ProviderLimiter
from providers.quota import QuotaLedger
from providers.tomtom import TomTomGeocoder, TomTomRouter
from providers.transport import HttpxClient, TomTomTransport, TransportConfig
from providers.weather import OpenMeteoWeather

from apps.routing.service import AnalysisService


@lru_cache(maxsize=1)
def get_service() -> AnalysisService:
    """Share limiter, quota ledger and weather cache across IPs in this process."""
    config = settings.PROVIDER_CONFIG

    def clock() -> datetime:
        return datetime.now(UTC)

    client = HttpxClient()
    limiter = ProviderLimiter(
        time.monotonic,
        time.sleep,
        requests_per_second=cast(int, config["requests_per_second"]),
        concurrency=cast(int, config["call_concurrency"]),
    )
    ledger = QuotaLedger(
        clock,
        daily_limit=cast(int, config["weather_daily_quota_units"]),
        request_limit=cast(int, config["weather_request_unit_limit"]),
    )
    transport = TomTomTransport(
        client,
        cast(str, config["tomtom_api_key"]),
        limiter,
        clock,
        time.sleep,
        TransportConfig(
            cast(float, config["connect_timeout_seconds"]),
            cast(float, config["routing_timeout_seconds"]),
            cast(float, config["geocode_timeout_seconds"]),
            cast(int, config["max_retries"]),
            cast(float, config["retry_backoff_seconds"]),
        ),
    )
    weather = OpenMeteoWeather.from_mapping(
        config, client=client, clock=clock, sleeper=time.sleep, limiter=limiter, ledger=ledger
    )
    seconds = min(float(cast(float, config["analysis_deadline_seconds"])), 35)
    service = AnalysisService(
        geocoder=TomTomGeocoder(transport),
        router=TomTomRouter(transport, clock),
        weather=weather,
        ledger=ledger,
        clock=clock,
        monotonic=time.monotonic,
        deadline_factory=lambda: Deadline(seconds, time.monotonic),
        request_id=lambda: str(uuid4()),
        deadline_seconds=seconds,
        max_coordinates=cast(int, config["max_coordinates"]),
        max_route_distance_miles=cast(float, config["max_route_distance_miles"]),
    )
    atexit.register(client.close)
    atexit.register(transport.close)
    atexit.register(weather.close)
    atexit.register(service.close)
    return service
