"""Stable identifiers for normalized, directed WGS84 route geometry."""

from fractions import Fraction
from hashlib import sha256

from domain.route_types import Route


def stable_route_id(route: Route) -> str:
    """Hash ordered lon/lat microdegrees, rounded half-even for identity only.

    The versioned ASCII form is ``route-geometry-v1|lon,lat;lon,lat;...``,
    with integer microdegrees and signed zero normalized to zero. Canonical
    Route geometry already removes consecutive duplicate vertices. Vertex order
    and density remain significant: reversing a traveled path changes identity.
    Coordinate mapping-key order and provider alternatives order are irrelevant.
    No geometry, mileage, duration or risk comparison value is quantized.
    """
    points = (
        f"{round(Fraction(str(p.longitude)) * 10**6)},{round(Fraction(str(p.latitude)) * 10**6)}"
        for p in route.geometry
    )
    canonical = "route-geometry-v1|" + ";".join(points)
    return "route_" + sha256(canonical.encode("ascii")).hexdigest()
