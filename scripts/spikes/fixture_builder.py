"""User-approved synthetic TomTom shapes; these are never live provider results."""
import json

from common import FIXTURES, save
from geometry import distance

meta = {"provenance": "SYNTHETIC: user approved replacement on 2026-10-10", "reason": "real TomTom result storage permission unresolved under section 11.4", "live_result": False}
routes = []
for index in range(3):
    vertices = [(34, -100), (34.005+index*.006, -99.99), (34.02, -99.98)]
    first = round(distance(vertices[0], vertices[1]))
    length = first+round(distance(vertices[1], vertices[2]))
    summary = {"lengthInMeters": length, "travelTimeInSeconds": 200+index*20}
    points = [{"latitude": lat, "longitude": lon} for lat, lon in vertices]
    routes.append({"summary": summary, "legs": [{"summary": summary, "points": points}],
                   "sections": [{"startPointIndex": 0, "endPointIndex": 2, "sectionType": "TRAVEL_MODE", "travelMode": "truck"}],
                   "progress": [{"pointIndex": 0, "distanceInMeters": 0, "travelTimeInSeconds": 0},
                                {"pointIndex": 2, "distanceInMeters": length, "travelTimeInSeconds": summary["travelTimeInSeconds"]}]})
save(FIXTURES / "routing_three_routes.json", {"formatVersion": "0.0.12", "routes": routes, "_fixture": {**meta, "trim": "invented three-vertex geometry, sparse endpoint progress; no copied provider geometry"}})
summary = {"query": "exampleville", "queryType": "NON_NEAR", "numResults": 1, "totalResults": 1}
save(FIXTURES / "geocoding.json", {"summary": summary, "results": [{"type": "Geography", "score": 2, "address": {"municipality": "Exampleville", "countryCode": "US"}, "position": {"lat": 34, "lon": -100}}], "_fixture": meta})
save(FIXTURES / "geocoding_empty.json", {"summary": {**summary, "numResults": 0, "totalResults": 0}, "results": [], "_fixture": meta})
save(FIXTURES / "invalid_key.json", {"status": 401, "body": {"detailedError": {"code": "Unauthorized", "message": "Invalid credentials"}}, "_fixture": {**meta, "basis": "observed status and error structure; message invented"}})
save(FIXTURES / "no_route.json", {"status": 400, "body": {"formatVersion": "0.0.12", "detailedError": {"code": "NO_ROUTE_FOUND", "message": "Synthetic disconnected road networks"}}, "_fixture": {**meta, "basis": "observed disconnected-network status and code; message invented"}})
save(FIXTURES / "quota_exceeded.json", {"status": 429, "body": None, "_fixture": {**meta, "basis": "documented quota status; live body UNVERIFIED; quota deliberately not exhausted"}})
print(json.dumps({"synthetic_tomtom_fixtures": 6, "real_tomtom_payloads_in_fixtures": 0}))
