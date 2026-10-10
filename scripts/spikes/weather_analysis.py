"""Offline observed weather normalization, classifications and horizon evidence."""
import copy
import json
from collections import Counter
from datetime import UTC, datetime, timedelta

from common import FIXTURES, OUT, save
from weather_probe import FIELDS


def classify(wind, rain, snow):
    wind_level = 1 + sum(wind >= n for n in (25, 35, 45, 55))
    rain_level = 5 if rain > 1 else 1 + sum(rain >= n for n in (.10, .25, .50))
    snow_level = 5 if snow > 3 else 1 + sum(snow >= n for n in (.5, 1, 2))
    return max(wind_level, rain_level, snow_level)


def iso(timestamp):
    return datetime.fromtimestamp(timestamp, UTC).isoformat()


if __name__ == "__main__":
    report = {}
    threshold_observations = {}
    for name in ("batch_50_48h", "batch_100_48h", "horizon_16_days", "short_model_16_days"):
        objects = json.loads((OUT / (name+"_weather.json")).read_text())
        counts, examples, maxima = Counter(), {}, dict.fromkeys(FIELDS, 0)
        for obj in objects:
            hourly = obj["hourly"]
            assert obj["hourly_units"] == {"time": "unixtime", "wind_speed_10m": "mp/h", "rain": "inch", "showers": "inch", "snowfall": "inch"}
            for i, timestamp in enumerate(hourly["time"]):
                raw = {field: hourly[field][i] for field in FIELDS}
                if any(value is None for value in raw.values()):
                    counts["UNKNOWN"] += 1
                    continue
                normalized = {"wind_mph": raw["wind_speed_10m"], "rain_in_per_hour": raw["rain"]+raw["showers"], "snow_in_per_hour": raw["snowfall"]}
                level = classify(*normalized.values())
                for field, value in normalized.items():
                    threshold_observations.setdefault(field, {}).setdefault(str(value), {"value": value, "timestamp_utc": iso(timestamp)})
                counts[str(level)] += 1
                examples.setdefault(str(level), {"timestamp_utc": iso(timestamp), "raw": raw, "normalized": normalized, "hazard_level": level})
                for field in FIELDS:
                    maxima[field] = max(maxima[field], raw[field])
        report[name] = {"locations": len(objects), "first_utc": iso(objects[0]["hourly"]["time"][0]), "last_utc": iso(objects[0]["hourly"]["time"][-1]), "counts": dict(counts), "examples": examples, "maxima": maxima}
    raw = json.loads((OUT / "short_model_16_days_weather.json").read_text())
    fixture = copy.deepcopy(raw[:1])
    null_index = next(i for i, v in enumerate(fixture[0]["hourly"][FIELDS[0]]) if v is None)
    fixture[0]["hourly"] = {field: values[null_index-1:null_index+2] for field, values in fixture[0]["hourly"].items()}
    fixture[0]["_fixture"] = {"provenance": "real Open-Meteo ICON global forecast", "trim": "first location; last valid hour and first two null hours, all arrays trimmed together"}
    save(FIXTURES / "weather_null.json", fixture)
    horizon_request = json.loads((OUT / "horizon_16_days_summary.json").read_text())["request"]
    now = datetime.fromisoformat(horizon_request["sent_utc"])
    required_end = now + timedelta(days=7, hours=48)
    report["horizon_check"] = {"sample_now_utc": now.isoformat(), "latest_departure_utc": (now+timedelta(days=7)).isoformat(), "required_slider_end_utc": required_end.isoformat(), "covered": required_end.timestamp() <= raw[0]["hourly"]["time"][-1], "required_data": "best_match horizon probe has no nulls; ICON tail is unavailable despite timestamps"}
    thresholds = {"wind_mph": (25, 35, 45, 55), "rain_in_per_hour": (.10, .25, .50, 1), "snow_in_per_hour": (.5, 1, 2, 3)}
    report["observed_exact_boundaries"] = {field: [row for row in threshold_observations[field].values() if row["value"] in bounds] for field, bounds in thresholds.items()}
    save(OUT / "weather_analysis.json", report)
    print(json.dumps(report))
