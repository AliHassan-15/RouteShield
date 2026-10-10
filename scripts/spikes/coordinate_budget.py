"""Offline effect of a 100-coordinate cap on mandatory D04 checkpoints."""
import bisect
import itertools
import json
import math

from common import OUT, save
from geometry import distance, points

body = json.loads((OUT / "long_truck_repeated_routes.json").read_text())
pooled, counts = set(), []
for route in body["routes"]:
    vertices = points(route)
    chain = [0.0]
    for a, b in itertools.pairwise(vertices):
        chain.append(chain[-1]+distance(a, b))
    length, step = chain[-1], 50*1609.344
    stations = [i*step for i in range(math.ceil(length/step))]+[length]
    for station in stations:
        index = min(bisect.bisect_right(chain, station)-1, len(vertices)-2)
        span = chain[index+1]-chain[index]
        f = (station-chain[index])/span if span else 0
        a, b = vertices[index:index+2]
        pooled.add((a[0]+f*(b[0]-a[0]), a[1]+f*(b[1]-a[1])))
    counts.append(len(stations))
deduplicated = []
for point in sorted(pooled):
    if not any(distance(point, other) <= 100 for other in deduplicated):
        deduplicated.append(point)
result = {"interval_miles": 50, "per_route_checkpoints": counts, "exact_unique_mandatory_coordinates": len(pooled), "deduplicated_within_100m": len(deduplicated), "proposed_100_cap_fits": len(deduplicated) <= 100, "density_reduction_from_300": 2/3, "maximum_duration_seconds": max(r["summary"]["travelTimeInSeconds"] for r in body["routes"])}
save(OUT / "coordinate_budget.json", result)
print(json.dumps(result))
