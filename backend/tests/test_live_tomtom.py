"""OPTIONAL live evidence: at most one routing + one geocoding request, no recordings.

Run once with ROUTESHIELD_LIVE_TOMTOM=1 and a local TOMTOM_API_KEY. Ordinary
pytest runs skip this test and forbid network. Prints only normalized findings.
"""

import os
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from time import monotonic, perf_counter, sleep
from typing import cast

import httpx
import pytest
from django.conf import settings
from domain.route_types import Coordinate
from providers.deadline import Deadline
from providers.errors import ErrorCode, ProviderError
from providers.limiter import ProviderLimiter
from providers.tomtom import RoutingPolicy, TomTomGeocoder, TomTomRouter
from providers.transport import HTTPResponse, HttpxClient, TomTomTransport, TransportConfig


@pytest.mark.skipif(
    os.environ.get("ROUTESHIELD_LIVE_TOMTOM") != "1"
    or not settings.PROVIDER_CONFIG["tomtom_api_key"],
    reason="Requires explicit live flag and locally configured TomTom key.",
)
def test_tomtom_live_smoke() -> None:
    config = settings.PROVIDER_CONFIG
    native = HttpxClient()

    class CountingClient:
        calls = 0

        def get(
            self,
            url: str,
            *,
            params: Sequence[tuple[str, str]],
            timeout: httpx.Timeout,
            deadline: Deadline,
        ) -> HTTPResponse:
            self.calls += 1
            if self.calls > 2:
                raise AssertionError("Live smoke request budget exceeded.")
            return native.get(url, params=params, timeout=timeout, deadline=deadline)

    client = CountingClient()

    def clock() -> datetime:
        return datetime.now(UTC)

    limiter = ProviderLimiter(
        monotonic,
        sleep,
        requests_per_second=cast(int, config["requests_per_second"]),
        concurrency=cast(int, config["call_concurrency"]),
    )
    transport = TomTomTransport(
        client,
        cast(str, config["tomtom_api_key"]),
        limiter,
        clock,
        sleep,
        TransportConfig(
            connect_seconds=cast(float, config["connect_timeout_seconds"]),
            routing_read_seconds=cast(float, config["routing_timeout_seconds"]),
            geocode_read_seconds=cast(float, config["geocode_timeout_seconds"]),
            geocode_retries=0,
            backoff_seconds=cast(float, config["retry_backoff_seconds"]),
        ),
    )
    router = TomTomRouter(
        transport, clock, policy=RoutingPolicy(max_fallback_calls=0), allow_past_recovery=False
    )
    geocoder = TomTomGeocoder(transport)
    # Fixed public Los Angeles-area coordinates, no user addresses or personal data.
    departure = clock() - timedelta(seconds=60)
    deadline = Deadline(cast(float, config["analysis_deadline_seconds"]), monotonic)
    route_ok = geocode_ok = False
    try:
        started = perf_counter()
        try:
            result = router.route_alternatives(
                Coordinate(-118.2437, 34.0522),
                Coordinate(-118.4912, 34.0195),
                departure,
                deadline=deadline,
            )
            route_ok = True
            print(
                f"LIVE routing: success; distinct_routes={len(result.routes)}; "
                f"profile={result.profile}; traffic=false; past_departAt=accepted; "
                f"seconds={perf_counter() - started:.3f}"
            )
        except ProviderError as error:
            # Either acceptance or a correctly normalized explicit past-time
            # rejection answers this probe. A rejection does not verify route data.
            route_ok = error.code is ErrorCode.INVALID_REQUEST and error.past_departure_rejected
            print(
                f"LIVE routing: {error.code.value}; "
                f"past_departAt_rejected={error.past_departure_rejected}; "
                f"seconds={perf_counter() - started:.3f}"
            )
        started = perf_counter()
        try:
            result_geo = geocoder.geocode("Santa Monica California", deadline=deadline)
            geocode_ok = True
            print(
                f"LIVE geocoding: success; candidates={len(result_geo.candidates)}; "
                f"attribution_confirmed={result_geo.attribution.confirmed}; "
                f"seconds={perf_counter() - started:.3f}"
            )
        except ProviderError as error:
            print(f"LIVE geocoding: {error.code.value}; seconds={perf_counter() - started:.3f}")
        print(
            f"LIVE request count={client.calls}; maximum=2; retries=0; waypoint calls=0; "
            f"past-time recovery=disabled; routing_read_cap={config['routing_timeout_seconds']}s"
        )
    finally:
        transport.close()
        native.close()
    assert client.calls <= 2
    assert route_ok and geocode_ok, "See safe LIVE findings above; no repeat authorized."
