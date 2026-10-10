# Provider fixture provenance

- **VERIFIED:** `weather_batch.json` contains the first two locations and three hours of the real 50-location Open-Meteo response. Every hourly array was trimmed together.
- **VERIFIED:** `weather_null.json` contains one real ICON-global location, its last valid hour and first two null hours. Nulls have not been replaced with zeros.
- **VERIFIED:** These weather data are supplied by [Open-Meteo](https://open-meteo.com/), under [CC BY 4.0](https://open-meteo.com/en/licence); modifications are the trimming described above. Provider grid coordinates are public trip-corridor samples, unrelated to any person's whereabouts.
- **VERIFIED:** All six TomTom fixtures are **SYNTHETIC**, approved by the user on 2026-10-10 because permission to preserve real responses remains unresolved. They model observed structures; they are not recordings or successful live results. Synthetic route geometry is unsuitable for testing live distinctness.
- **UNVERIFIED:** `quota_exceeded.json` models documented HTTP 429 with an unknown body (`null`). No account quota was exhausted. An adapter must tolerate non-JSON errors; this fixture does not establish TomTom's live 429 body.
- **UNVERIFIED:** Real TomTom fixtures remain incomplete pending storage permission. The approved replacement avoids copying route/geocode data into the commit.

## Adapter task synthetic cases (2026-10-10)

`tests/provider_helpers.py` builds invented polylines, consistent geometric
meters and explicit sparse cumulative timing; it never records live responses.
Routing/geocoding tests also use the six synthetic files above. Generated
JSON/XML/empty errors, malformed/missing fields, waypoint responses and dense
2,800-mile routes live directly in the corresponding test modules. Their
numeric values are test inputs, not observed provider measurements. New tests
do not load either historical real weather fixture. The optional live test
prints safe findings only and writes no response file.
