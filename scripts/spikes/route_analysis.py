"""Offline shape/timing/overlap checks, never a production adapter."""
import itertools
import json

from common import OUT, save
from geometry import analyze, distance, points


def timing(route):
    vertices = points(route)
    progress = route.get("progress", [])
    summary = route["summary"]
    checks = {"vertex_count": len(vertices), "progress_count": len(progress),
              "same_length": len(vertices) == len(progress), "summary": {key: summary[key] for key in ("lengthInMeters", "travelTimeInSeconds")}}
    checks["valid_anchors"] = bool(progress) and progress[0]["pointIndex"] == 0 and progress[-1]["pointIndex"] == len(vertices)-1
    for field in ("pointIndex", "distanceInMeters", "travelTimeInSeconds"):
        checks[field + "_monotonic"] = all(a[field] <= b[field] for a, b in itertools.pairwise(progress))
    checks["final_matches"] = bool(progress) and progress[-1]["distanceInMeters"] == summary["lengthInMeters"] and progress[-1]["travelTimeInSeconds"] == summary["travelTimeInSeconds"]
    checks["first"] = progress[0] if progress else None
    checks["last"] = progress[-1] if progress else None
    checks["usable"] = checks["valid_anchors"] and checks["final_matches"] and all(checks[f+"_monotonic"] for f in ("pointIndex", "distanceInMeters", "travelTimeInSeconds"))
    # Demonstrate provider-approved interpolation using geometry chainage, not uniform speed.
    chain = [0]
    for a, b in itertools.pairwise(vertices):
        chain.append(chain[-1]+distance(a, b))
    expanded = {}
    for field in ("distanceInMeters", "travelTimeInSeconds"):
        values = [None]*len(vertices)
        for a, b in itertools.pairwise(progress):
            start, end = a["pointIndex"], b["pointIndex"]
            span = chain[end]-chain[start]
            for i in range(start, end+1):
                f = (chain[i]-chain[start])/span if span else 0
                values[i] = a[field]+f*(b[field]-a[field])
        expanded[field] = {"length": len(values), "nulls": values.count(None), "first": values[0], "last": values[-1],
                           "monotonic": all(a <= b for a, b in itertools.pairwise(values) if a is not None and b is not None)}
    checks["expanded_using_anchors"] = expanded
    return checks


if __name__ == "__main__":
    report = {}
    for path in sorted(OUT.glob("*_routes.json")):
        routes = json.loads(path.read_text()).get("routes", [])
        if not routes:
            continue
        value = {"timing": [timing(r) for r in routes], "overlap": analyze(routes)}
        report[path.stem] = value
        print(json.dumps({"label": path.stem, "timing": value["timing"], "overlap": value["overlap"]}))
    save(OUT / "route_analysis.json", report)
