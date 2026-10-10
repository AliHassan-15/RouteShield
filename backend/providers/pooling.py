"""Pure deterministic mandatory-first coordinate deduplication and uniform coarsening."""

from collections.abc import Sequence
from fractions import Fraction
from types import MappingProxyType

from domain.route_policy import DEFAULT_ROUTE_POLICY
from domain.route_types import Coordinate, RouteError

from providers.contracts import PointAssignment, PointKey, PoolingResult, PoolPoint
from providers.distinctness import point_distance
from providers.errors import ErrorCode, ProviderError

POOL_TOLERANCE_M = 100
POOL_CAP = 200
RADIUS_M = float(DEFAULT_ROUTE_POLICY.earth_radius_m)


def _sorted(points: Sequence[PoolPoint], mandatory: bool) -> tuple[PoolPoint, ...]:
    if any(
        not isinstance(p, PoolPoint)
        or not isinstance(p.key, PointKey)
        or not isinstance(p.key.route_id, str)
        or not p.key.route_id
        or type(p.key.index) is not int
        or p.key.index < 0
        or p.key.mandatory is not mandatory
        or not isinstance(p.coordinate, Coordinate)
        or (
            p.distance_m is not None
            and (not isinstance(p.distance_m, Fraction) or p.distance_m < 0)
        )
        for p in points
    ):
        raise ProviderError(ErrorCode.INVALID_REQUEST)
    return tuple(
        sorted(
            points,
            key=lambda p: (
                p.key.route_id,
                p.key.index,
                p.coordinate.longitude,
                p.coordinate.latitude,
            ),
        )
    )


def _representative(point: Coordinate, pool: Sequence[Coordinate]) -> int | None:
    # <=200 representatives bounds this simple exact spherical comparison; it
    # avoids order-sensitive grid-cell rounding at the 100m boundary.
    return next(
        (i for i, p in enumerate(pool) if point_distance(point, p, RADIUS_M) <= POOL_TOLERANCE_M),
        None,
    )


def pool_coordinates(
    mandatory: Sequence[PoolPoint], optional: Sequence[PoolPoint] = (), *, cap: int = POOL_CAP
) -> PoolingResult:
    """First stable point represents later points within100m, mandatory tier first.

    Optional candidates use a common increasing index stride per route, keeping
    endpoint candidates. If even that minimum cannot fit, optional sampling is
    suppressed uniformly and disclosed; mandatory samples still serve the corridor.
    Coarsened optional mappings are explicitly approximate, never checkpoint weather.
    """
    if type(cap) is not int or not 1 <= cap <= POOL_CAP:
        raise ProviderError(ErrorCode.INVALID_REQUEST)
    required, extra = _sorted(mandatory, True), _sorted(optional, False)
    all_points = (*required, *extra)
    if not required or len({p.key for p in all_points}) != len(all_points):
        raise ProviderError(ErrorCode.INVALID_REQUEST)
    pool: list[Coordinate] = []
    assignments: dict[PointKey, PointAssignment] = {}
    for p in required:
        index = _representative(p.coordinate, pool)
        if index is None:
            index = len(pool)
            pool.append(p.coordinate)
        assignments[p.key] = PointAssignment(
            index, point_distance(p.coordinate, pool[index], RADIUS_M)
        )
    if len(pool) > cap:
        raise RouteError("TRIP_TOO_LARGE", "Mandatory pooled coordinates exceed the approved cap.")
    mandatory_count = len(pool)
    groups: dict[str, list[PoolPoint]] = {}
    for point in extra:
        groups.setdefault(point.key.route_id, []).append(point)
    max_count = max((len(g) for g in groups.values()), default=0)
    stride = 1
    selected: tuple[PoolPoint, ...] = ()
    final_pool = list(pool)
    for stride in range(1, max_count + 2):
        chosen = tuple(
            p
            for group in groups.values()
            for i, p in enumerate(group)
            if i % stride == 0 or i == len(group) - 1
        )
        candidate_pool = list(pool)
        for p in chosen:
            if _representative(p.coordinate, candidate_pool) is None:
                candidate_pool.append(p.coordinate)
        if len(candidate_pool) <= cap:
            selected, final_pool = chosen, candidate_pool
            break
    else:
        stride, selected = max_count + 1, ()
    selected_keys = {p.key for p in selected}
    for point in extra:
        index = _representative(point.coordinate, final_pool)
        coarsened = point.key not in selected_keys
        if index is None:
            index = min(
                range(len(final_pool)),
                key=lambda i: (point_distance(point.coordinate, final_pool[i], RADIUS_M), i),
            )
            coarsened = True
        assignments[point.key] = PointAssignment(
            index, point_distance(point.coordinate, final_pool[index], RADIUS_M), coarsened
        )
    density: dict[str, float] = {}
    for route_id, group in groups.items():
        represented = [p for p in group if p.key in selected_keys]
        if len(represented) < 2:
            density[route_id] = 0
        elif all(p.distance_m is not None for p in represented):
            positions = [float(p.distance_m) for p in represented if p.distance_m is not None]
            density[route_id] = max(b - a for a, b in zip(positions, positions[1:], strict=False))
        else:
            density[route_id] = max(
                point_distance(a.coordinate, b.coordinate, RADIUS_M)
                for a, b in zip(represented, represented[1:], strict=False)
            )
    return PoolingResult(
        tuple(final_pool),
        mandatory_count,
        MappingProxyType(assignments),
        len(extra),
        len(selected),
        stride,
        MappingProxyType(density),
        ("OPTIONAL_COORDINATES_COARSENED",) if len(selected) < len(extra) else (),
    )
