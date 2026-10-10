"""RANK-04: directed canonical geometry IDs, independent of response order."""

from dataclasses import replace
from hashlib import sha256

import pytest
from domain.identity import stable_route_id
from domain.recommendation import recommend_routes
from domain.route_types import Coordinate, Route, RouteError

from tests.ranking_helpers import option
from tests.route_helpers import straight_route


def geometry_route(points: tuple[tuple[float, float], ...]) -> Route:
    """Identity uses only geometry; synthetic timing is irrelevant to this test."""
    return replace(straight_route(1), geometry=tuple(Coordinate(*p) for p in points))


def test_documented_canonical_form_and_signed_zero() -> None:
    route = geometry_route(((-0.0, 0), (1, -2)))
    # Hand-specified integer microdegrees, longitude first, traveled order intact.
    expected = "route_" + sha256(b"route-geometry-v1|0,0;1000000,-2000000").hexdigest()
    assert stable_route_id(route) == expected
    assert stable_route_id(route) == stable_route_id(geometry_route(((0, -0.0), (1, -2))))


@pytest.mark.parametrize(
    ("value", "quantized"),
    [
        (0.00000049, 0),
        (0.0000005, 0),
        (0.00000051, 1),
        (0.0000015, 2),
        (0.0000025, 2),
        (-0.0000005, 0),
        (-0.0000015, -2),
    ],
)
def test_identity_only_half_even_microdegree_quantization(value: float, quantized: int) -> None:
    route = geometry_route(((value, value), (1, 2)))
    canonical = f"route-geometry-v1|{quantized},{quantized};1000000,2000000"
    expected = "route_" + sha256(canonical.encode("ascii")).hexdigest()
    assert stable_route_id(route) == expected
    assert route.geometry[0].longitude == value  # Original precision is untouched.


def test_reverse_direction_and_different_vertex_density_remain_distinct() -> None:
    route = geometry_route(((0, 0), (1, 0)))
    assert stable_route_id(route) != stable_route_id(geometry_route(((1, 0), (0, 0))))
    assert stable_route_id(route) != stable_route_id(geometry_route(((0, 0), (0.5, 0), (1, 0))))


def test_coordinate_mapping_key_reordering_does_not_change_normalized_id() -> None:
    # Mapping order is irrelevant once explicit lon/lat normalization has happened.
    first = ({"longitude": 0.0, "latitude": 0.0}, {"longitude": 1.0, "latitude": 2.0})
    second = ({"latitude": 0.0, "longitude": 0.0}, {"latitude": 2.0, "longitude": 1.0})
    a = geometry_route(tuple((p["longitude"], p["latitude"]) for p in first))
    b = geometry_route(tuple((p["longitude"], p["latitude"]) for p in second))
    assert stable_route_id(a) == stable_route_id(b)


def test_quantization_collision_fails_instead_of_using_input_order() -> None:
    first = option(0)
    second = replace(
        first,
        route=replace(
            first.route,
            geometry=tuple(
                Coordinate(p.longitude + 0.00000001, p.latitude) for p in first.route.geometry
            ),
        ),
    )
    assert first.route.geometry != second.route.geometry
    assert stable_route_id(first.route) == stable_route_id(second.route)
    with pytest.raises(RouteError) as error:
        recommend_routes((first, second))
    assert error.value.code == "DUPLICATE_ROUTE_ID"
