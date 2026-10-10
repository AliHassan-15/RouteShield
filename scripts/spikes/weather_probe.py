"""Live forecast batches/horizon and six uncached 50-location analysis batches."""
import copy
import json
import sys
from datetime import UTC, datetime, timedelta
from itertools import pairwise

from common import FIXTURES, OUT, request, save
from geometry import points, samples

FIELDS = ["wind_speed_10m", "rain", "showers", "snowfall"]
BASE = [("hourly", ",".join(FIELDS)), ("wind_speed_unit", "mph"),
        ("precipitation_unit", "inch"), ("timezone", "UTC"), ("timeformat", "unixtime")]


def locations(count):
    route_file = OUT / "long_truck_repeated_routes.json"
    if route_file.exists() and "routes" in json.loads(route_file.read_text()):
        routes = json.loads(route_file.read_text())["routes"]
        pool = list(dict.fromkeys(q for route in routes for q, _ in samples(points(route))))
        return [pool[round(i*(len(pool)-1)/(count-1))] for i in range(count)]
    raise SystemExit("Raw corridor input removed. Recollection needs confirmed TomTom storage permission.")


def probe(label, coords, extra):
    params = BASE + [("latitude", ",".join(str(p[0]) for p in coords)),
                     ("longitude", ",".join(str(p[1]) for p in coords))] + extra
    row, body = request("open_meteo", label, "/v1/forecast", params)
    objects = body if isinstance(body, list) else [body] if "hourly" in body else []
    summaries = []
    for obj in objects:
        hourly = obj["hourly"]
        timestamps = hourly["time"]
        summaries.append({"latitude": obj["latitude"], "longitude": obj["longitude"],
                          "units": obj["hourly_units"], "hours": len(timestamps),
                          "first": timestamps[0], "last": timestamps[-1],
                          "hourly_steps": sorted({b-a for a, b in pairwise(timestamps)}),
                          "nulls": {f: sum(v is None for v in hourly.get(f, [])) for f in FIELDS},
                          "missing": [f for f in FIELDS if f not in hourly],
                          "timezone": obj["timezone"]})
    save(OUT / (label + "_summary.json"), {"request": row, "parameters": extra, "locations": summaries, "error": body if not objects else None})
    save(OUT / (label + "_weather.json"), body)
    print({"label": label, "locations": len(objects), "first_location": summaries[:1], "nulls": sum(sum(s["nulls"].values()) for s in summaries)})
    if objects and not (FIXTURES / "weather_batch.json").exists():
        fixture = copy.deepcopy(objects[:2])
        for obj in fixture:
            obj["hourly"] = {k: v[:3] for k, v in obj["hourly"].items()}
        fixture[0]["_fixture"] = {"provenance": "real Open-Meteo", "trim": "first 2 locations and 3 hours; all hourly arrays trimmed together"}
        save(FIXTURES / "weather_batch.json", fixture)
    return row, objects


if __name__ == "__main__":
    mode = sys.argv[1]
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    window = [("start_hour", now.strftime("%Y-%m-%dT%H:%M")), ("end_hour", (now+timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M"))]
    if mode == "analysis":
        coords = locations(300)
        route = json.loads((OUT / "long_truck_repeated_routes.json").read_text())
        seconds = max(r["summary"]["travelTimeInSeconds"] for r in route["routes"])
        end = now+timedelta(hours=max(49, int(seconds/3600)+2))
        window[-1] = ("end_hour", end.strftime("%Y-%m-%dT%H:%M"))
        for start in range(0, 300, 50):
            probe("analysis_300_batch_"+str(start//50+1), coords[start:start+50], window)
    elif mode == "horizon":
        probe("horizon_16_days", locations(50), [("forecast_days", 16)])
    elif mode == "missing":
        probe("short_model_16_days", locations(2), [("forecast_days", 16), ("models", "icon_global")])
    else:
        probe("batch_"+mode+"_48h", locations(int(mode)), window)
