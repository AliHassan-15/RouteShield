"""Exact D09 probe first; prints only shapes and numeric checks, never URLs."""
import sys

from common import OUT, request, save
from geometry import analyze
from route_analysis import timing

TRIPS = {"urban": [(34.0094, -118.4973), (34.0537, -118.2427)],
         "medium": [(41.8781, -87.6298), (42.3314, -83.0458)],
         "long": [(34.0537, -118.2427), (40.7128, -74.0060)]}


def probe(name, points, mode="truck", repeat=False, alternatives=2, extended="repeated"):
    params = [("maxAlternatives", alternatives), ("alternativeType", "anyRoute"),
              ("travelMode", mode), ("routeRepresentation", "polyline"), ("traffic", "false")]
    if extended == "repeated":
        params += [("extendedRouteRepresentation", "distance"), ("extendedRouteRepresentation", "travelTime")]
    else:
        params += [("extendedRouteRepresentation", extended)]
    if "--fixed" in sys.argv:
        params += [("departAt", "2026-10-11T12:00:00Z")]
        name += "_fixed"
    label = name + "_" + mode + ("_repeat" if repeat else "") + "_" + extended.replace(",", "_")
    locations = ":".join(f"{lat},{lon}" for lat, lon in points)
    row, body = request("tomtom", label, "/routing/1/calculateRoute/" + locations + "/json", params)
    routes = body.get("routes", [])
    checks = []
    for route in routes:
        vertices = [p for leg in route["legs"] for p in leg["points"]]
        checks.append({"summary": {key: route["summary"][key] for key in ("lengthInMeters", "travelTimeInSeconds")}, "vertices": len(vertices),
                       "point_keys": list(vertices[0]),
                       "route_keys": list(route), "leg_keys": list(route["legs"][0])})
    save(OUT / (label + "_shape.json"), {"request": row, "parameters_without_key": params,
                                          "checks": checks, "error": body if not routes else None})
    if "--record-raw" in sys.argv:
        save(OUT / (label + "_routes.json"), body)  # Requires separately confirmed storage permission.
    if routes:
        save(OUT / (label + "_metrics.json"), {"timing": [timing(r) for r in routes], "overlap": analyze(routes)})
    print({"label": label, "route_count": len(routes), "shapes": checks, "error": body if not routes else None})
    return row, body


if __name__ == "__main__":
    name = sys.argv[1]
    probe(name, TRIPS[name], repeat="--repeat" in sys.argv,
          mode="car" if "--car" in sys.argv else "truck",
          extended="distance,travelTime" if "--comma" in sys.argv else "repeated")
