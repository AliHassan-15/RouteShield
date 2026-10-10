"""CP-04/05 and ROUTE-02/06: hand-calculated geometry/timing and safe failure."""

import json
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import TypedDict, cast

import pytest
from domain.geometry import build_route, elapsed_at, geometric_chainage, interpolate_coordinate
from domain.route_policy import DEFAULT_ROUTE_POLICY
from domain.route_types import (
    Coordinate,
    Route,
    RouteError,
    RouteNumber,
    TimingAnchor,
    TimingSource,
)

from tests.route_helpers import anchor, straight_route

F = Fraction


def test_unequal_segment_speeds_follow_provider_anchors() -> None:
    """10 mi takes 600 s, next 10 mi takes 1200 s: mile15 is 600+600, not 1350."""
    route = straight_route(20, positions_miles=(0, 10, 20), times_s=(0, 600, 1800))
    assert elapsed_at(route, 15 * route.policy.meters_per_mile) == 1200
    assert elapsed_at(route, F(0)) == 0 and elapsed_at(route, route.distance_m) == 1800
    assert tuple(elapsed_at(route, i * route.policy.meters_per_mile) for i in range(21)) == (
        *tuple(F(i * 60) for i in range(11)),
        *tuple(F(600 + (i - 10) * 120) for i in range(11, 21)),
    )


def test_curved_geometry_uses_traveled_segments_not_endpoint_shortcut() -> None:
    """An L shape travels two one-degree arcs; its bend is not on the endpoint chord."""
    geometry = (Coordinate(0, 0), Coordinate(1, 0), Coordinate(1, 1))
    distances = geometric_chainage(geometry)
    route = build_route(
        geometry,
        distances[-1],
        500,
        cumulative_distances_m=distances,
        cumulative_times_s=(0, 100, 500),
    )
    assert interpolate_coordinate(route, distances[1]) == geometry[1]
    first = interpolate_coordinate(route, distances[1] / 2)
    second = interpolate_coordinate(route, (distances[1] + distances[2]) / 2)
    assert (first.longitude, first.latitude) == pytest.approx((0.5, 0), abs=1e-10)
    assert (second.longitude, second.latitude) == pytest.approx((1, 0.5), abs=1e-10)
    assert distances[-1] > geometric_chainage((geometry[0], geometry[-1]))[-1]


@pytest.mark.parametrize(
    "geometry,expected_lat",
    [
        ((Coordinate(179, 0), Coordinate(-179, 0)), 0),
        ((Coordinate(0, 89), Coordinate(180, 89)), 90),
    ],
)
def test_antimeridian_and_polar_minor_arcs(
    geometry: tuple[Coordinate, ...], expected_lat: int
) -> None:
    """Both midpoints follow the short two-degree arc, not a longitude-zero detour."""
    distances = geometric_chainage(geometry)
    route = build_route(
        geometry,
        distances[-1],
        600,
        progress_anchors=(anchor(0, 0, 0), anchor(1, distances[-1], 600)),
    )
    midpoint = interpolate_coordinate(route, route.distance_m / 2)
    assert midpoint.latitude == pytest.approx(expected_lat, abs=1e-9)
    if expected_lat == 0:
        assert abs(midpoint.longitude) == pytest.approx(180, abs=1e-9)
    assert -180 <= midpoint.longitude <= 180


def test_loop_geometry_is_valid_and_chainage_does_not_sort_axes() -> None:
    """Returning to the origin after a bend still travels nonzero distance."""
    geometry = (Coordinate(0, 0), Coordinate(1, 0), Coordinate(0, 0))
    distances = geometric_chainage(geometry)
    route = build_route(
        geometry,
        distances[-1],
        600,
        cumulative_distances_m=distances,
        cumulative_times_s=(0, 200, 600),
    )
    assert route.distance_m > 0 and route.geometry[0] == route.geometry[-1]
    assert interpolate_coordinate(route, distances[1]) == Coordinate(1, 0)


@pytest.mark.parametrize("distance_factor", [F("1.02"), F(".98")])
def test_provider_geometry_disagreement_is_not_silently_rescaled(distance_factor: Fraction) -> None:
    route = straight_route(100)
    with pytest.raises(RouteError, match="chainage disagree") as error:
        build_route(
            route.geometry,
            route.distance_m * distance_factor,
            600,
            progress_anchors=(anchor(0, 0, 0), anchor(1, route.distance_m * distance_factor, 600)),
        )
    assert error.value.code == "GEOMETRY_DISTANCE_MISMATCH"


def test_every_anchor_span_is_reconciled_not_just_the_total() -> None:
    """Correct overall length cannot disguise mile10 claimed at the mile5 vertex."""
    route = straight_route(20, positions_miles=(0, 5, 20), times_s=(0, 200, 600))
    with pytest.raises(RouteError) as error:
        build_route(
            route.geometry,
            route.distance_m,
            600,
            cumulative_distances_m=(0, 10 * route.policy.meters_per_mile, route.distance_m),
            cumulative_times_s=(0, 200, 600),
        )
    assert error.value.code == "NO_VALID_TIMING"
    assert isinstance(error.value.__cause__, RouteError)
    assert error.value.__cause__.code == "GEOMETRY_DISTANCE_MISMATCH"


@pytest.mark.parametrize(
    "distances,times",
    [
        ((0, 10), (0, 300, 600)),  # mismatched vertex count
        ((0, 10, 20), (0, 600)),
        ((0, 11, 10), (0, 300, 600)),  # decreasing distance/end
        ((0, 10, 20), (0, 500, 400)),  # decreasing elapsed/end
        ((1, 10, 20), (0, 300, 600)),  # nonzero starting distance
        ((0, 10, 20), (1, 300, 600)),  # nonzero starting time
        ((0, 10, 19), (0, 300, 600)),  # wrong endpoint
        ((0, 10, 20), (0, 300, 590)),
        ((0, 10, 20), (0, 599.5, 599)),  # pinning must not hide a raw decrease
    ],
)
def test_invalid_arrays_only_use_valid_guidance(
    distances: tuple[int, ...],
    times: tuple[float, ...],
) -> None:
    """All bad arrays fail without guidance; explicit valid guidance preserves unequal speeds."""
    route = straight_route(20, positions_miles=(0, 10, 20), times_s=(0, 200, 600))
    values = tuple(F(value) * route.policy.meters_per_mile for value in distances)
    with pytest.raises(RouteError) as error:
        build_route(
            route.geometry,
            route.distance_m,
            600,
            cumulative_distances_m=values,
            cumulative_times_s=times,
        )
    assert error.value.code == "NO_VALID_TIMING"
    recovered = build_route(
        route.geometry,
        route.distance_m,
        600,
        cumulative_distances_m=values,
        cumulative_times_s=times,
        guidance_anchors=route.timing_anchors,
    )
    assert recovered.timing_source is TimingSource.GUIDANCE
    assert recovered.timing_warnings[0].code == "GUIDANCE_TIMING_FALLBACK"
    assert recovered.timing_warnings[0].rejected_code is not None
    assert elapsed_at(recovered, 15 * route.policy.meters_per_mile) == 400  # 200+half of400


def test_missing_or_bad_guidance_does_not_invent_even_spread_timing() -> None:
    route = straight_route(20)
    for guidance in ((), (anchor(0, 0, 0), anchor(1, route.distance_m, 500))):
        with pytest.raises(RouteError) as error:
            build_route(route.geometry, route.distance_m, 600, guidance_anchors=guidance)
        assert error.value.code == "NO_VALID_TIMING"


def test_sparse_progress_expands_by_geometric_chainage() -> None:
    """Five geometry vertices but three anchors: mile5 maps to300 s, mile15 to1200 s."""
    route = straight_route(
        20, positions_miles=(0, 5, 10, 15, 20), times_s=(0, 100, 600, 1500, 1800)
    )
    progress = (
        anchor(0, 0, 0),
        anchor(2, 10 * route.policy.meters_per_mile, 600),
        anchor(4, route.distance_m, 1800),
    )
    result = build_route(route.geometry, route.distance_m, 1800, progress_anchors=progress)
    assert result.timing_source is TimingSource.PROGRESS
    assert len(result.cumulative_times_s) == 5 and len(result.timing_anchors) == 3
    assert float(result.cumulative_times_s[1]) == pytest.approx(300)
    assert float(result.cumulative_times_s[3]) == pytest.approx(1200)
    assert result.cumulative_times_s[0] == 0 and result.cumulative_times_s[-1] == 1800


def test_duplicate_points_collapse_and_retain_stationary_waits() -> None:
    """Wait60 s at origin and120 s halfway; mile15 ETA is510 s, not distance-fraction450."""
    base = straight_route(20, positions_miles=(0, 10, 20), times_s=(0, 300, 600))
    geometry = (
        base.geometry[0],
        base.geometry[0],
        base.geometry[1],
        base.geometry[1],
        base.geometry[2],
    )
    distances = (
        0,
        0,
        10 * base.policy.meters_per_mile,
        10 * base.policy.meters_per_mile,
        base.distance_m,
    )
    route = build_route(
        geometry,
        base.distance_m,
        600,
        cumulative_distances_m=distances,
        cumulative_times_s=(0, 60, 300, 420, 600),
    )
    assert route.geometry == base.geometry and len(route.timing_anchors) == 5
    assert tuple(a.point_index for a in route.timing_anchors) == (0, 0, 1, 1, 2)
    assert elapsed_at(route, F(0)) == 0
    assert elapsed_at(route, 5 * base.policy.meters_per_mile) == 180  # 60 + half of240
    assert elapsed_at(route, 10 * base.policy.meters_per_mile) == 300  # first arrival before wait
    assert route.cumulative_times_s[1] == 300
    assert elapsed_at(route, 15 * base.policy.meters_per_mile) == 510  # 420 + half of180


def test_duplicate_destination_preserves_last_time_and_coordinate() -> None:
    route = straight_route(5)
    geometry = (*route.geometry, route.geometry[-1])
    collapsed = build_route(
        geometry,
        route.distance_m,
        700,
        cumulative_distances_m=(0, route.distance_m, route.distance_m),
        cumulative_times_s=(0, 600, 700),
    )
    assert len(collapsed.geometry) == 2 and len(collapsed.timing_anchors) == 3
    assert elapsed_at(collapsed, collapsed.distance_m) == 700


def test_endpoint_tolerances_are_explicit_and_snapped_to_summary() -> None:
    route = straight_route(20)
    result = build_route(
        route.geometry,
        route.distance_m,
        600,
        progress_anchors=(anchor(0, 0, 0), anchor(1, route.distance_m + 1, 601)),
    )
    assert result.timing_anchors[-1].distance_m == route.distance_m
    assert result.timing_anchors[-1].elapsed_s == 600
    assert result.timing_warnings[-1].code == "TIMING_ENDPOINT_RECONCILED"
    strict = replace(
        DEFAULT_ROUTE_POLICY, distance_endpoint_tolerance_m=F(0), time_endpoint_tolerance_s=F(0)
    )
    with pytest.raises(RouteError):
        build_route(
            route.geometry,
            route.distance_m,
            600,
            policy=strict,
            progress_anchors=(anchor(0, 0, 0), anchor(1, route.distance_m + 1, 601)),
        )


@pytest.mark.parametrize(
    "longitude,latitude",
    [(181, 0), (-181, 0), (0, 91), (0, -91), (float("nan"), 0), (0, float("inf")), (True, 0)],
)
def test_invalid_wgs84_coordinates(longitude: float, latitude: float) -> None:
    with pytest.raises(RouteError):
        Coordinate(longitude, latitude)


@pytest.mark.parametrize(
    "geometry",
    [
        (),
        (Coordinate(0, 0),),
        (Coordinate(0, 0), Coordinate(0, 0)),
        (Coordinate(0, 0), Coordinate(180, 0)),
    ],
)
def test_insufficient_or_ambiguous_geometry(geometry: tuple[Coordinate, ...]) -> None:
    with pytest.raises(RouteError):
        build_route(geometry, 100, 100)


@pytest.mark.parametrize("field", ["distance", "duration", "anchor_distance", "anchor_time"])
@pytest.mark.parametrize(
    "bad", [-1, float("nan"), float("inf"), float("-inf"), True, Decimal("sNaN"), "not-a-number"]
)
def test_bad_numeric_route_inputs(field: str, bad: object) -> None:
    route = straight_route(20)
    value = cast(RouteNumber, bad)
    progress = (
        anchor(0, 0, 0),
        TimingAnchor(
            1,
            cast(Fraction, value) if field == "anchor_distance" else route.distance_m,
            cast(Fraction, value) if field == "anchor_time" else F(600),
        ),
    )
    with pytest.raises(RouteError):
        build_route(
            route.geometry,
            value if field == "distance" else route.distance_m,
            value if field == "duration" else 600,
            progress_anchors=progress,
        )


@pytest.mark.parametrize("index", [-1, 2, True, 0.5])
def test_bad_anchor_indices(index: int) -> None:
    route = straight_route(20)
    with pytest.raises(RouteError):
        build_route(
            route.geometry,
            route.distance_m,
            600,
            progress_anchors=(anchor(0, 0, 0), anchor(index, route.distance_m, 600)),
        )


def test_moving_zero_chainage_and_stationary_distance_are_rejected() -> None:
    route = straight_route(20, positions_miles=(0, 10, 20), times_s=(0, 300, 600))
    with pytest.raises(RouteError):
        build_route(
            route.geometry,
            route.distance_m,
            600,
            cumulative_distances_m=(0, 0, route.distance_m),
            cumulative_times_s=(0, 300, 600),
        )
    with pytest.raises(RouteError):
        build_route(
            (route.geometry[0], route.geometry[0], route.geometry[-1]),
            route.distance_m,
            600,
            cumulative_distances_m=(0, 1, route.distance_m),
            cumulative_times_s=(0, 10, 600),
        )


class FixturePoint(TypedDict):
    longitude: float
    latitude: float


class FixtureLeg(TypedDict):
    points: list[FixturePoint]


class FixtureSummary(TypedDict):
    lengthInMeters: int
    travelTimeInSeconds: int


class FixtureProgress(TypedDict):
    pointIndex: int
    distanceInMeters: int
    travelTimeInSeconds: int


class FixtureRoute(TypedDict):
    legs: list[FixtureLeg]
    summary: FixtureSummary
    progress: list[FixtureProgress]


def synthetic_fixture_route(record: FixtureRoute) -> Route:
    """Test-only projection of the observed JSON shape, never a production adapter."""
    geometry = tuple(
        Coordinate(point["longitude"], point["latitude"])
        for leg in record["legs"]
        for point in leg["points"]
    )
    return build_route(
        geometry,
        record["summary"]["lengthInMeters"],
        record["summary"]["travelTimeInSeconds"],
        progress_anchors=tuple(
            anchor(value["pointIndex"], value["distanceInMeters"], value["travelTimeInSeconds"])
            for value in record["progress"]
        ),
    )


def test_synthetic_provider_fixture_shape_fits_route_model() -> None:
    path = Path(__file__).parent / "fixtures" / "providers" / "routing_three_routes.json"
    fixture = cast(dict[str, list[FixtureRoute]], json.loads(path.read_text(encoding="utf-8")))
    for record in fixture["routes"]:
        route = synthetic_fixture_route(record)
        assert len(route.geometry) == 3 and len(route.timing_anchors) == 2
        assert route.timing_source is TimingSource.PROGRESS
        assert len(route.cumulative_times_s) == len(route.cumulative_distances_m) == 3
        assert route.distance_m == record["summary"]["lengthInMeters"]
        assert route.duration_s == record["summary"]["travelTimeInSeconds"]
        assert route.geometry[0] == Coordinate(-100, 34)


def test_route_values_are_immutable() -> None:
    route = straight_route(20)
    for target, field, value in (
        (route, "duration_s", F(0)),
        (route.geometry[0], "latitude", 1),
        (route.timing_anchors[0], "elapsed_s", F(10)),
        (route.policy, "checkpoint_budget", 2),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(target, field, value)


def test_route_factory_copies_mutable_sequences() -> None:
    route = straight_route(20)
    coordinates = list(route.geometry)
    times = [0, 600]
    copied = build_route(
        coordinates,
        route.distance_m,
        600,
        cumulative_distances_m=route.cumulative_distances_m,
        cumulative_times_s=times,
    )
    coordinates.clear()
    times[-1] = 100
    assert copied == route


@pytest.mark.parametrize(
    "geometry", [None, "not-geometry", ((0, 0), (1, 1)), (Coordinate(0, 0), None)]
)
def test_malformed_geometry_is_a_clear_domain_error(geometry: object) -> None:
    from collections.abc import Sequence

    with pytest.raises(RouteError) as error:
        build_route(cast(Sequence[Coordinate], geometry), 100, 100)
    assert error.value.code == "INVALID_GEOMETRY"


def test_progress_index_order_must_not_decrease() -> None:
    route = straight_route(30, positions_miles=(0, 10, 20, 30), times_s=(0, 100, 300, 600))
    with pytest.raises(RouteError) as error:
        build_route(
            route.geometry,
            route.distance_m,
            600,
            progress_anchors=(
                anchor(0, 0, 0),
                anchor(2, 10 * route.policy.meters_per_mile, 100),
                anchor(1, 20 * route.policy.meters_per_mile, 300),
                anchor(3, route.distance_m, 600),
            ),
        )
    assert error.value.code == "NO_VALID_TIMING"
    assert isinstance(error.value.__cause__, RouteError)
    assert error.value.__cause__.code == "DECREASING_TIMING"


def test_geometry_reconciliation_tolerance_is_configurable() -> None:
    route = straight_route(100)
    policy = replace(
        DEFAULT_ROUTE_POLICY,
        geometry_relative_tolerance=F(".03"),
        geometry_absolute_tolerance_m=F(0),
    )
    distance = route.distance_m * F("1.02")
    relaxed = build_route(
        route.geometry,
        distance,
        600,
        policy=policy,
        progress_anchors=(anchor(0, 0, 0), anchor(1, distance, 600)),
    )
    assert relaxed.distance_m == distance
    assert relaxed.distance_miles == 102


def test_earth_radius_and_duplicate_tolerance_are_policy_parameters() -> None:
    geometry = (Coordinate(0, 0), Coordinate(1, 0))
    ordinary = geometric_chainage(geometry)[-1]
    radius = replace(DEFAULT_ROUTE_POLICY, earth_radius_m=DEFAULT_ROUTE_POLICY.earth_radius_m * 2)
    assert float(geometric_chainage(geometry, radius)[-1]) == pytest.approx(float(ordinary * 2))
    tiny = (Coordinate(0, 0), Coordinate(0.000000001, 0))
    assert geometric_chainage(tiny)[-1] == 0
    strict = replace(DEFAULT_ROUTE_POLICY, duplicate_point_tolerance_m=F(0))
    assert geometric_chainage(tiny, strict)[-1] > 0


def test_antipodal_rejection_tolerance_is_configurable() -> None:
    geometry = (Coordinate(0, 0), Coordinate(179.99, 0))
    assert geometric_chainage(geometry)[-1] > 0
    relaxed_arc_limit = replace(DEFAULT_ROUTE_POLICY, antipodal_tolerance_radians=0.001)
    with pytest.raises(RouteError) as error:
        geometric_chainage(geometry, relaxed_arc_limit)
    assert error.value.code == "AMBIGUOUS_SEGMENT"


@pytest.mark.parametrize("distance", [F(-1), F(100000)])
def test_out_of_route_chainage_is_rejected(distance: Fraction) -> None:
    route = straight_route(5)
    for operation in (elapsed_at, interpolate_coordinate):
        with pytest.raises(RouteError) as error:
            operation(route, distance)
        assert error.value.code == "INVALID_CHAINAGE"


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), Decimal("sNaN")])
def test_interpolation_validates_numeric_chainage(value: object) -> None:
    route = straight_route(5)
    for operation in (elapsed_at, interpolate_coordinate):
        with pytest.raises(RouteError) as error:
            operation(route, cast(Fraction, value))
        assert error.value.code == "INVALID_NUMBER"
