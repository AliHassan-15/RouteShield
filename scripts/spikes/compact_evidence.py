"""Keep numeric audit evidence rather than bulky provider data."""
import json
from collections import Counter

from common import OUT, save

raw = json.loads((OUT / "route_analysis.json").read_text())
metrics = {}
for name, analysis in raw.items():
    rows = []
    for source in analysis["timing"]:
        row = {key: value for key, value in source.items() if key != "summary"}
        row["length_meters"] = source["summary"]["lengthInMeters"]
        row["duration_seconds"] = source["summary"]["travelTimeInSeconds"]
        rows.append(row)
    metrics[name] = {"timing": rows, "overlap": analysis["overlap"]}
save(OUT / "routing_metrics.json", metrics)
geocoding = {}
for path in OUT.glob("geocode_*.json"):
    source = json.loads(path.read_text())
    geocoding[path.stem] = {"request": source["request"], "query": source["query"], "summary": source["body"].get("summary"),
                          "candidates": [{"score": row["score"], "type": row["type"], "place": row["address"].get("municipality"), "region": row["address"].get("countrySubdivision")} for row in source["body"].get("results", [])]}
save(OUT / "geocoding_metrics.json", geocoding)
requests = json.loads((OUT / "requests.json").read_text())
accounting = {}
for provider in ("tomtom", "open_meteo"):
    rows = [row for row in requests if row["provider"] == provider]
    accounting[provider] = {"attempts": len(rows), "completed_http": sum(isinstance(row["status"], int) for row in rows), "statuses": dict(Counter(str(row["status"]) for row in rows))}
analysis = [row for row in requests if row["label"].startswith("analysis_300_batch_")]
accounting["analysis_300"] = {"http_requests": len(analysis), "serial_request_seconds": round(sum(row["seconds"] for row in analysis), 3), "response_bytes": sum(row["bytes"] for row in analysis), "published_units": 300, "actual_charged_units": "UNVERIFIED: no quota metadata returned"}
save(OUT / "accounting.json", accounting)
print(json.dumps(accounting))
