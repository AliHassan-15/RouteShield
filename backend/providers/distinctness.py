"""Pure D09 geometry comparison, kept in providers under the domain edit limit.

A three-dimensional spatial grid avoids polar/antimeridian projection errors.
Fine great-circle subsegments bound each grid box; exact spherical arc distance
decides matching. Grid padding never changes the 100 m matching threshold.
"""

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import atan2, cos, degrees, floor, hypot, radians, sin

from domain.identity import stable_route_id
from domain.route_types import Coordinate, Route

type Vector = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class DistinctnessPolicy:
    step_m: Fraction = Fraction("804.672")  # 0.5 statute mile, geometric chainage.
    tolerance_m: float = 100
    maximum_overlap: Fraction = Fraction(9, 10)
    cell_m: float = 1000
    maximum_segment_m: float = 500
    grid_padding_m: float = 0.01  # Covers the subsegment arc's bounding-box bulge only.


DISTINCTNESS = DistinctnessPolicy()


def _dot(a: Vector, b: Vector) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _cross(a: Vector, b: Vector) -> Vector:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def _vector(p: Coordinate) -> Vector:
    lat, lon = radians(p.latitude), radians(p.longitude)
    return cos(lat) * cos(lon), cos(lat) * sin(lon), sin(lat)


def _angle(a: Vector, b: Vector) -> float:
    return atan2(hypot(*_cross(a, b)), _dot(a, b))


def _between(a: Vector, b: Vector, fraction: float) -> Vector:
    angle = _angle(a, b)
    if angle == 0:
        return a
    wa, wb = sin((1 - fraction) * angle) / sin(angle), sin(fraction * angle) / sin(angle)
    result = tuple(wa * x + wb * y for x, y in zip(a, b, strict=True))
    norm = hypot(*result)
    return result[0] / norm, result[1] / norm, result[2] / norm


def _coordinate(vector: Vector) -> Coordinate:
    return Coordinate(
        degrees(atan2(vector[1], vector[0])), degrees(atan2(vector[2], hypot(vector[0], vector[1])))
    )


def point_distance(a: Coordinate, b: Coordinate, radius: float) -> float:
    """Spherical distance, independent of provider units and vertex density."""
    return _angle(_vector(a), _vector(b)) * radius


def arc_distance(point: Vector, a: Vector, b: Vector, radius: float) -> float:
    """Distance to the minor great-circle segment, clamped to its endpoints."""
    normal = _cross(a, b)
    squared = _dot(normal, normal)
    best = min(_angle(point, a), _angle(point, b))
    if squared == 0:
        return best * radius
    factor = _dot(point, normal) / squared
    projected = tuple(q - factor * n for q, n in zip(point, normal, strict=True))
    norm = hypot(*projected)
    if norm == 0:
        return best * radius
    p: Vector = (projected[0] / norm, projected[1] / norm, projected[2] / norm)
    if _dot(point, p) < 0:
        p = (-p[0], -p[1], -p[2])
    # Oriented cross products test arc membership without an angular epsilon.
    if _dot(_cross(a, p), normal) >= 0 and _dot(_cross(p, b), normal) >= 0:
        best = min(best, _angle(point, p))
    return best * radius


@dataclass(frozen=True, slots=True)
class WeightedSample:
    coordinate: Coordinate
    owned_m: Fraction


def weighted_samples(
    route: Route, policy: DistinctnessPolicy = DISTINCTNESS
) -> tuple[WeightedSample, ...]:
    """Sample geometric chainage; endpoints/final remainder own midpoint half-segments."""
    chain = route.geometric_distances_m
    length = chain[-1]
    count = int(length // policy.step_m)
    stations = tuple(i * policy.step_m for i in range(count + 1))
    if stations[-1] != length:
        stations = (*stations, length)
    boundaries = (
        Fraction(0),
        *((a + b) / 2 for a, b in zip(stations, stations[1:], strict=False)),
        length,
    )
    vectors = tuple(_vector(p) for p in route.geometry)
    samples = []
    for i, station in enumerate(stations):
        index = min(bisect_right(chain, station) - 1, len(chain) - 2)
        ratio = float((station - chain[index]) / (chain[index + 1] - chain[index]))
        point = _coordinate(_between(vectors[index], vectors[index + 1], ratio))
        samples.append(WeightedSample(point, boundaries[i + 1] - boundaries[i]))
    return tuple(samples)


class PolylineIndex:
    """Ephemeral geometric acceleration structure, never a provider-result cache."""

    def __init__(self, route: Route, policy: DistinctnessPolicy = DISTINCTNESS) -> None:
        self.radius = float(route.policy.earth_radius_m)
        self.policy = policy
        self._grid: dict[tuple[int, int, int], list[tuple[Vector, Vector]]] = {}
        vectors = tuple(_vector(p) for p in route.geometry)
        padding = policy.tolerance_m + policy.grid_padding_m
        for a, b in zip(vectors, vectors[1:], strict=False):
            divisions = max(1, int(_angle(a, b) * self.radius / policy.maximum_segment_m) + 1)
            previous = a
            for i in range(1, divisions + 1):
                following = _between(a, b, i / divisions)
                ranges = tuple(
                    range(
                        floor((min(x, y) * self.radius - padding) / policy.cell_m),
                        floor((max(x, y) * self.radius + padding) / policy.cell_m) + 1,
                    )
                    for x, y in zip(previous, following, strict=True)
                )
                for x in ranges[0]:
                    for y in ranges[1]:
                        for z in ranges[2]:
                            self._grid.setdefault((x, y, z), []).append((previous, following))
                previous = following

    def matches(self, point: Coordinate) -> bool:
        """The cutoff is inclusive <=100 m, with no matching epsilon shift."""
        vector = _vector(point)
        cell = tuple(floor(v * self.radius / self.policy.cell_m) for v in vector)
        return any(
            arc_distance(vector, a, b, self.radius) <= self.policy.tolerance_m
            for a, b in self._grid.get((cell[0], cell[1], cell[2]), ())
        )


def directional_overlap(samples: Sequence[WeightedSample], target: PolylineIndex) -> Fraction:
    """Matched owned length divided by total length; preserve exact sample weights."""
    total = sum((sample.owned_m for sample in samples), Fraction(0))
    matched = sum(
        (sample.owned_m for sample in samples if target.matches(sample.coordinate)), Fraction(0)
    )
    return matched / total


def symmetric_overlap(a: Route, b: Route, policy: DistinctnessPolicy = DISTINCTNESS) -> Fraction:
    """Use max of both directional coverages, detecting contained near-clones."""
    return max(
        directional_overlap(weighted_samples(a, policy), PolylineIndex(b, policy)),
        directional_overlap(weighted_samples(b, policy), PolylineIndex(a, policy)),
    )


def overlap_is_duplicate(overlap: Fraction, policy: DistinctnessPolicy = DISTINCTNESS) -> bool:
    """Exactly 0.90 is allowed; the rejection operator is strictly greater."""
    return overlap > policy.maximum_overlap


def distinct_routes(
    routes: Sequence[Route], policy: DistinctnessPolicy = DISTINCTNESS
) -> tuple[Route, ...]:
    """Canonical-ID filtering is independent of provider order; keep up to three."""
    accepted: list[tuple[Route, tuple[WeightedSample, ...], PolylineIndex]] = []
    for route in sorted(routes, key=lambda r: (stable_route_id(r), r.duration_s, r.distance_m)):
        samples, index = weighted_samples(route, policy), PolylineIndex(route, policy)
        if all(
            not overlap_is_duplicate(
                max(
                    directional_overlap(samples, other_index),
                    directional_overlap(other_samples, index),
                ),
                policy,
            )
            for _, other_samples, other_index in accepted
        ):
            accepted.append((route, samples, index))
            if len(accepted) == 3:
                break
    return tuple(route for route, _, _ in accepted)
