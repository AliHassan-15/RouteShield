"""Candidate normalization/ordering, sanitized lookups and no result cache."""

from dataclasses import FrozenInstanceError
from fractions import Fraction

import pytest
from providers.errors import ErrorCode, ProviderError
from providers.tomtom import TomTomGeocoder, parse_candidates, sanitize_query

from tests.provider_helpers import ORIGIN, FakeClient, FakeTime, fixture, response, transport


@pytest.mark.parametrize(
    "query,expected",
    [
        ("  New\t York\n ", "New York"),
        ("A\x00bc", "Abc"),
        ("Ab\u200bc", "Abc"),
        ("abc", "abc"),
        ("x" * 200, "x" * 200),
    ],
)
def test_query_sanitization(query: str, expected: str) -> None:
    assert sanitize_query(query) == expected


@pytest.mark.parametrize("query", ["", " ", "x", "ab", "x" * 201, "\x00\x01"])
def test_invalid_query_never_calls_provider(query: str) -> None:
    clock = FakeTime()
    client = FakeClient([])
    adapter = transport(client, clock)
    try:
        with pytest.raises(ProviderError) as caught:
            TomTomGeocoder(adapter).geocode(query, deadline=clock.deadline())
        assert caught.value.code is ErrorCode.INVALID_REQUEST and client.calls == []
    finally:
        adapter.close()


def test_candidate_order_ties_bounded_list_and_stable_id() -> None:
    values = [
        {
            "type": "Geography",
            "score": 2,
            "position": {"lat": 34, "lon": -100 + i},
            "address": {
                "freeformAddress": f"Place {i}",
                "country": "United States",
                "countryCode": "US",
                "countrySubdivision": "TX",
            },
        }
        for i in range(7)
    ]
    result = parse_candidates({"results": values})
    assert len(result) == 5 and [c.label for c in result] == [f"Place {i}" for i in range(5)]
    assert result[0].coordinate == ORIGIN and result[0].score == Fraction(2)
    assert result[0].region == "TX" and result[0].country == "United States"
    assert result == parse_candidates({"results": values})
    assert len({c.candidate_id for c in result}) == 5
    with pytest.raises(FrozenInstanceError):
        result[0].label = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "item",
    [
        {},
        {
            "type": "Geography",
            "score": True,
            "position": {"lat": 34, "lon": -100},
            "address": {"municipality": "Place"},
        },
        {
            "type": "Geography",
            "score": 2,
            "position": {"lat": 91, "lon": -100},
            "address": {"municipality": "Place"},
        },
        {
            "type": "Geography",
            "score": float("nan"),
            "position": {"lat": 34, "lon": -100},
            "address": {"municipality": "Place"},
        },
    ],
)
def test_candidate_missing_malformed_values(item: object) -> None:
    with pytest.raises(ProviderError):
        parse_candidates({"results": [item]})


@pytest.mark.parametrize(
    "countries,expected", [((), None), (("US",), "US"), (("US", "CAN"), "US,CAN")]
)
def test_optional_country_restriction_and_attribution(
    countries: tuple[str, ...], expected: str | None
) -> None:
    clock = FakeTime()
    client = FakeClient([response(fixture("geocoding.json"))])
    adapter = transport(client, clock)
    try:
        result = TomTomGeocoder(adapter, countries=countries).geocode(
            " New York ", deadline=clock.deadline()
        )
        url, params, _ = client.calls[0]
        assert "/New%20York.json" in url and dict(params).get("countrySet") == expected
        assert "typeahead" not in dict(params) and dict(params)["storeResult"] == "false"
        assert result.attribution.provider == "TomTom" and result.attribution.confirmed is False
        assert "pending" in result.attribution.text
        assert len(client.calls) == 1  # No Copyright API request.
    finally:
        adapter.close()


def test_empty_geocoding_and_repeated_requests_are_uncached() -> None:
    clock = FakeTime()
    client = FakeClient([response(fixture("geocoding_empty.json"))] * 2)
    adapter = transport(client, clock)
    geocoder = TomTomGeocoder(adapter)
    try:
        for _ in range(2):
            assert geocoder.geocode("Unknown place", deadline=clock.deadline()).candidates == ()
        assert len(client.calls) == 2
        assert not any(name.endswith("cache") for name in vars(geocoder))
    finally:
        adapter.close()


@pytest.mark.parametrize("countries", [("us",), ("USA1",), ("U",)])
def test_invalid_restriction(countries: tuple[str, ...]) -> None:
    clock = FakeTime()
    adapter = transport(FakeClient([]), clock)
    try:
        with pytest.raises(ProviderError):
            TomTomGeocoder(adapter, countries=countries)
    finally:
        adapter.close()
