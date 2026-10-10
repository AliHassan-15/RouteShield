"""Reusable normalized adapter contracts, exercised with TomTom and trivial fakes."""

from collections.abc import Iterator
from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest
from domain.route_types import Coordinate, Route
from providers.contracts import (
    PENDING_ATTRIBUTION,
    GeocodeResult,
    GeocodingProvider,
    RoutingProvider,
    RoutingResult,
)
from providers.deadline import Deadline
from providers.tomtom import TomTomGeocoder, TomTomRouter, parse_candidates, parse_routes

from tests.provider_helpers import (
    DESTINATION,
    NOW,
    ORIGIN,
    FakeClient,
    FakeTime,
    fixture,
    response,
    transport,
)


class FakeRouter:
    def route_alternatives(
        self,
        origin: Coordinate,
        destination: Coordinate,
        departure: datetime,
        *,
        deadline: Deadline,
    ) -> RoutingResult:
        deadline.check()
        return RoutingResult(
            parse_routes(fixture("routing_three_routes.json")),
            (),
            PENDING_ATTRIBUTION,
            departure,
            departure,
        )


class FakeGeocoder:
    def geocode(self, query: str, *, deadline: Deadline) -> GeocodeResult:
        deadline.check()
        return GeocodeResult(parse_candidates(fixture("geocoding.json")), PENDING_ATTRIBUTION)


@pytest.fixture(params=("tomtom", "fake"))
def routing_provider(request: pytest.FixtureRequest) -> Iterator[RoutingProvider]:
    clock = FakeTime()
    adapter = transport(FakeClient([response(fixture("routing_three_routes.json"))]), clock)
    yield TomTomRouter(adapter, clock.utc) if request.param == "tomtom" else FakeRouter()
    adapter.close()


@pytest.fixture(params=("tomtom", "fake"))
def geocoding_provider(request: pytest.FixtureRequest) -> Iterator[GeocodingProvider]:
    clock = FakeTime()
    adapter = transport(FakeClient([response(fixture("geocoding.json"))]), clock)
    yield TomTomGeocoder(adapter) if request.param == "tomtom" else FakeGeocoder()
    adapter.close()


class RoutingAdapterContract:
    def test_normalized_routes_and_metadata(self, routing_provider: RoutingProvider) -> None:
        result = routing_provider.route_alternatives(
            ORIGIN, DESTINATION, NOW, deadline=FakeTime().deadline()
        )
        assert 1 <= len(result.routes) <= 3
        assert all(
            isinstance(r, Route) and r.distance_m > 0 and r.duration_s > 0 for r in result.routes
        )
        assert all(isinstance(point, Coordinate) for r in result.routes for point in r.geometry)
        assert result.submitted_departure == NOW
        assert result.profile == "truck" and result.live_traffic is False
        assert result.attribution.provider and result.attribution.text
        with pytest.raises(FrozenInstanceError):
            result.profile = "car"  # type: ignore[misc]


class GeocodingAdapterContract:
    def test_bounded_candidates_and_metadata(self, geocoding_provider: GeocodingProvider) -> None:
        result = geocoding_provider.geocode("Exampleville", deadline=FakeTime().deadline())
        assert 0 <= len(result.candidates) <= 5
        assert all(
            c.candidate_id and c.label and isinstance(c.coordinate, Coordinate)
            for c in result.candidates
        )
        assert result.attribution.provider and result.attribution.text
        with pytest.raises(FrozenInstanceError):
            result.candidates = ()  # type: ignore[misc]


class TestRoutingAdapterContract(RoutingAdapterContract):
    pass


class TestGeocodingAdapterContract(GeocodingAdapterContract):
    pass
