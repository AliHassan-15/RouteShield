"""Real ambiguous/partial/misspelled/empty geocoding and safe edge responses."""
import sys
from urllib.parse import quote

from common import OUT, request, save

CASES = {"ambiguous": ("Springfield", []),
         "autocomplete": ("Springf", [("typeahead", "true")]),
         "partial": ("Springf", []),
         "misspelled": ("350 Fift Avnue New York", []),
         "region": ("Springfield", [("lat", "42.10"), ("lon", "-72.59"), ("radius", "50000")]),
         "empty": ("Qzxqzxqzx Unexistent Boulevard 999999", [])}


def run(mode):
    if mode in {"invalid_key", "no_route", "disconnected"}:
        path = "/routing/1/calculateRoute/25,-140:25,-141/json"
        if mode == "disconnected":
            path = "/routing/1/calculateRoute/21.3069,-157.8583:34.0537,-118.2427/json"
        row, body = request("tomtom", mode, path, [("travelMode", "truck")], fake_key=mode == "invalid_key")
        save(OUT / (mode+"_error_metrics.json"), {"status": row["status"], "code": body.get("detailedError", {}).get("code"), "content_type": row.get("response_metadata", {}).get("content-type")})
        print({"case": mode, "status": row["status"], "body": body})
        return
    query, extra = CASES[mode]
    row, body = request("tomtom", "geocode_"+mode, "/search/2/geocode/"+quote(query, safe="")+".json",
                        [("countrySet", "US"), ("limit", "5")]+extra)
    if "--record-raw" in sys.argv:
        save(OUT / ("geocode_"+mode+".json"), {"request": row, "query": query, "body": body})
    results = body.get("results", [])
    print({"case": mode, "status": row["status"], "summary": body.get("summary"),
           "candidates": [{"score": r.get("score"), "type": r.get("type"), "address": r.get("address"), "position": r.get("position")} for r in results],
           "error": body if not results else None})


if __name__ == "__main__":
    run(sys.argv[1])
