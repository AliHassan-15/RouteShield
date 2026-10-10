"""WX-06, HEAT-01/06, API-08, BUDGET-01: preserve every mandatory original."""

import json
from fractions import Fraction
from math import degrees
from typing import cast

import pytest
from domain.route_types import Coordinate, RouteError
from providers.contracts import PointKey, PoolPoint
from providers.errors import ProviderError
from providers.pooling import RADIUS_M, pool_coordinates

from tests.provider_helpers import FIXTURES


def point(
    route: str, index: int, lon: float, *, mandatory: bool = True, meters: int | None = None
) -> PoolPoint:
    return PoolPoint(
        PointKey(route, index, mandatory),
        Coordinate(lon, 0),
        Fraction(meters) if meters is not None else None,
    )


@pytest.mark.parametrize("distance,merged", [(99.999, True), (100, True), (100.001, False)])
def test_100_meter_boundary(distance: float, merged: bool) -> None:
    required = [point("a", 0, 0), point("b", 0, degrees(distance / RADIUS_M))]
    result = pool_coordinates(required)
    assert len(result.coordinates) == (1 if merged else 2)
    assert result.assignments[required[0].key].pooled_index == 0
    assert result.assignments[required[1].key].pooled_index == (0 if merged else 1)


def test_stable_representative_mandatory_first_and_all_original_mappings() -> None:
    required = [point("b", 1, 0.02), point("a", 0, 0), point("b", 0, 0.0001)]
    optional = [point("a", 0, -0.05, mandatory=False), point("z", 0, 0.0002, mandatory=False)]
    result = pool_coordinates(required, optional)
    assert result == pool_coordinates(required[::-1], optional[::-1])
    assert result.coordinates[:2] == (Coordinate(0, 0), Coordinate(0.02, 0))
    assert result.coordinates[2] == Coordinate(-0.05, 0)
    assert result.mandatory_count == 2
    assert len(result.assignments) == 5
    assert result.assignments[required[2].key].pooled_index == 0
    assert result.assignments[optional[1].key].pooled_index == 0
    assert result.warnings == ()


def test_representatives_are_not_transitive_connected_components() -> None:
    result = pool_coordinates([point("a", i, degrees(i * 90 / RADIUS_M)) for i in range(3)])
    assert len(result.coordinates) == 2  # 0 represents90;180 is farther than100 from0.


def test_uniform_optional_coarsening_density_and_count() -> None:
    mandatory = [point("a", 0, -1)]
    extra = [point("a", i, i * 0.01, mandatory=False, meters=i * 1000) for i in range(100)]
    result = pool_coordinates(mandatory, extra, cap=11)
    assert len(result.coordinates) <= 11 and result.mandatory_count == 1
    assert result.optional_stride > 1
    assert result.optional_selected_count < result.optional_input_count == 100
    assert len(result.assignments) == 101
    assert result.actual_spacing_m["a"] == result.optional_stride * 1000
    assert result.warnings == ("OPTIONAL_COORDINATES_COARSENED",)
    for p in mandatory:
        assert not result.assignments[p.key].coarsened
    retained = [p for p in extra if not result.assignments[p.key].coarsened]
    assert retained[0].key.index == 0 and retained[-1].key.index == 99
    assert result == pool_coordinates(mandatory, extra[::-1], cap=11)


def test_no_optional_slots_uniform_suppression_still_maps_every_point() -> None:
    required = [point("a", i, i * 0.01) for i in range(200)]
    extra = [point("b", i, 5 + i * 0.01, mandatory=False) for i in range(20)]
    result = pool_coordinates(required, extra)
    assert len(result.coordinates) == 200 and result.optional_selected_count == 0
    assert all(result.assignments[p.key].coarsened for p in extra)
    assert len(result.assignments) == 220
    assert result.warnings


def test_mandatory_over_cap_reuses_domain_trip_too_large() -> None:
    with pytest.raises(RouteError) as caught:
        pool_coordinates([point("a", i, i * 0.01) for i in range(201)])
    assert caught.value.code == "TRIP_TOO_LARGE"


def test_long_trip_fixture_has_173_mandatory_and_optional_budget() -> None:
    manifest = json.loads((FIXTURES / "weather_long_trip_shape.json").read_text(encoding="utf-8"))
    assert manifest["live_result"] is False
    counts = cast(list[int], manifest["checkpoint_counts"])
    required = [
        PoolPoint(
            PointKey(str(route), i, True),
            Coordinate(-120, 34)
            if i == 0
            else Coordinate(-70, 34)
            if i == count - 1
            else Coordinate(-120 + i * 0.7, 34 + route),
            Fraction(i * 50 * 1609),
        )
        for route, count in enumerate(counts)
        for i in range(count)
    ]
    extra = [
        PoolPoint(PointKey(str(route), i, False), Coordinate(-119 + i * 0.1, 35 + route * 0.1))
        for route in range(3)
        for i in range(150)
    ]
    result = pool_coordinates(required, extra)
    assert counts == [58, 57, 62]
    assert result.mandatory_count == manifest["expected_unique_mandatory"] == 173
    assert len(result.coordinates) <= 200 and result.optional_stride > 1
    assert len(result.assignments) == 177 + 450
    assert all(not result.assignments[p.key].coarsened for p in required)


@pytest.mark.parametrize("bad", [0, 201, True, -1])
def test_invalid_cap(bad: int) -> None:
    with pytest.raises(ProviderError):
        pool_coordinates([point("a", 0, 0)], cap=bad)


def test_empty_duplicate_or_wrong_tier_is_rejected() -> None:
    p = point("a", 0, 0)
    for required, optional in [([], []), ([p, p], []), ([p], [p])]:
        with pytest.raises(ProviderError):
            pool_coordinates(required, optional)
