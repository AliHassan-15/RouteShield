"""ROUTE-03: independent D09 overlap, spatial cutoff and long-haul cases."""

from dataclasses import replace
from fractions import Fraction
from itertools import permutations
from math import degrees
from time import perf_counter

import pytest
from domain.identity import stable_route_id
from domain.route_policy import DEFAULT_ROUTE_POLICY
from domain.route_types import Coordinate
from providers.distinctness import (
    DISTINCTNESS,
    PolylineIndex,
    WeightedSample,
    directional_overlap,
    distinct_routes,
    overlap_is_duplicate,
    symmetric_overlap,
    weighted_samples,
)
from providers.tomtom import parse_route

from tests.provider_helpers import route_payload
from tests.route_helpers import straight_route


def test_identical_and_differently_sampled_polylines_are_duplicates() -> None:
    a = straight_route(3)
    b = straight_route(3, positions_miles=(0, 1, 3), times_s=(0, 100, 600))
    assert symmetric_overlap(a, a) == 1
    assert symmetric_overlap(a, b) == 1
    assert len(distinct_routes((a, b))) == 1


def test_containment_uses_maximum_of_directional_coverages() -> None:
    short, long = straight_route(1), straight_route(10)
    assert directional_overlap(weighted_samples(short), PolylineIndex(long)) == 1
    assert directional_overlap(weighted_samples(long), PolylineIndex(short)) < Fraction(1, 2)
    assert symmetric_overlap(short, long) == 1


@pytest.mark.parametrize("matched,duplicate", [(".8999", False), (".9", False), (".9001", True)])
def test_exact_owned_length_overlap_cutoff(matched: str, duplicate: bool) -> None:
    # Two measured positions and exact length ownership make the oracle independent
    # of floating-point coordinate/resampling errors at the 90% boundary.
    target = PolylineIndex(straight_route(2))
    weight = Fraction(matched)
    samples = (
        WeightedSample(Coordinate(0.01, 0), weight),
        WeightedSample(Coordinate(0.01, 1), 1 - weight),
    )
    overlap = directional_overlap(samples, target)
    assert overlap == weight
    assert overlap_is_duplicate(overlap) is duplicate


@pytest.mark.parametrize("offset_m,matched", [(99.99, True), (100.01, False)])
def test_parallel_roads_just_inside_and_outside_100m(offset_m: float, matched: bool) -> None:
    radius = float(DEFAULT_ROUTE_POLICY.earth_radius_m)
    latitude = degrees(offset_m / radius)
    index = PolylineIndex(straight_route(3))
    assert index.matches(Coordinate(0.01, latitude)) is matched
    parallel = parse_route(route_payload((Coordinate(0, latitude), Coordinate(0.04, latitude))))
    assert (symmetric_overlap(straight_route(3), parallel) > Fraction(9, 10)) is matched


def test_inclusive_distance_cutoff_has_no_epsilon() -> None:
    # Set the cutoff to the computed spherical distance, rather than pretending
    # rounded latitude denotes an exactly representable 100m distance.
    from providers.distinctness import point_distance

    radius = float(DEFAULT_ROUTE_POLICY.earth_radius_m)
    point = Coordinate(0.01, degrees(100 / radius))
    distance = point_distance(point, Coordinate(0.01, 0), radius)
    route = straight_route(2)
    assert PolylineIndex(route, replace(DISTINCTNESS, tolerance_m=distance)).matches(point)
    assert not PolylineIndex(route, replace(DISTINCTNESS, tolerance_m=distance - 0.0001)).matches(
        point
    )


def test_midpoint_ownership_includes_final_remainder_and_nonuniform_vertices() -> None:
    route = straight_route("1.2", positions_miles=(0, ".1", 1, "1.2"), times_s=(0, 10, 80, 100))
    samples = weighted_samples(route)
    length, step = route.geometric_distances_m[-1], DISTINCTNESS.step_m
    assert len(samples) == 4
    assert samples[0].owned_m == step / 2
    assert samples[1].owned_m == step
    assert samples[2].owned_m == (length - step) / 2
    assert samples[-1].owned_m == (length - 2 * step) / 2
    assert sum((s.owned_m for s in samples), Fraction(0)) == length
    assert samples[-1].coordinate.longitude == pytest.approx(route.geometry[-1].longitude)


def test_canonical_filter_is_independent_of_provider_order() -> None:
    routes = (
        parse_route(route_payload((Coordinate(0, 0), Coordinate(0.2, 0)))),
        parse_route(route_payload((Coordinate(0, 0), Coordinate(0.1, 0.1), Coordinate(0.2, 0)))),
        parse_route(route_payload((Coordinate(0, 0), Coordinate(0.1, -0.1), Coordinate(0.2, 0)))),
        parse_route(route_payload((Coordinate(0, 0), Coordinate(0.2, 0)), 700)),
    )
    expected = tuple(stable_route_id(r) for r in distinct_routes(routes))
    assert len(expected) == 3
    assert expected == tuple(sorted(expected))
    for order in permutations(routes):
        assert tuple(stable_route_id(r) for r in distinct_routes(order)) == expected


@pytest.mark.parametrize(
    "points",
    [
        (Coordinate(179, 0), Coordinate(-179, 0)),
        (Coordinate(-45, 89.5), Coordinate(45, 89.5)),
    ],
)
def test_spatial_index_handles_antimeridian_and_polar_arcs(points: tuple[Coordinate, ...]) -> None:
    route = parse_route(route_payload(points))
    assert directional_overlap(weighted_samples(route), PolylineIndex(route)) == 1


def test_2800_mile_synthetic_route_performance_bound() -> None:
    # Dense geometry and 5,602 half-mile samples: measure the complete comparison,
    # including index construction. The 5s bound has room for slower Linux CI.
    positions = tuple(Fraction(i, 2) for i in range(5601))
    times = tuple(Fraction(i) for i in range(5601))
    dense = straight_route(2800, positions_miles=positions, times_s=times)
    sparse = straight_route(2800)
    started = perf_counter()
    overlap = symmetric_overlap(dense, sparse)
    elapsed = perf_counter() - started
    assert overlap == 1
    assert elapsed < 5, f"2,800-mile comparison took {elapsed:.3f}s (bound 5s)."
    print(f"SYNTHETIC 2800mi overlap/index comparison: {elapsed:.3f}s; bound 5s")
