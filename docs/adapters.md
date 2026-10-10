# Routing and geocoding adapters — 2026-10-10

Implemented TomTom adapters under the approved D09/D11/D13/D19/D20/D21
contract. This task adds no weather implementation, API endpoint, frontend,
provider-result cache or persistence. All three user-owned release gates in
decisions.md remain OPEN; non-display development does not settle them.

## Boundaries and construction

`backend/providers/contracts.py` declares `RoutingProvider` and
`GeocodingProvider` protocols and frozen normalized candidate, attribution,
warning and result dataclasses. The user explicitly chose this location rather
than expanding the authorized domain edits. Only normalized `Coordinate`,
`Route` and these provider-neutral values cross the adapter boundary. No raw
TomTom payload, HTTP response or provider field name enters domain code.

Inject one shared `TomTomTransport` into `TomTomRouter` and `TomTomGeocoder`.
Its dependencies are `HTTPClient`, UTC clock, sleeper, `ProviderLimiter` and
`TransportConfig`. Each operation receives the **same** monotonic `Deadline`;
the later orchestration task must pass it through routing, fallback and weather.
Share the limiter across instances; separate limiters do not coordinate quotas.
Close transport/client at lifecycle shutdown. Production composition belongs to
the API task, not this adapter task. Country restriction is an optional
`TomTomGeocoder(countries=("US",))` constructor setting; default `()` deliberately
does not assume a country. Uppercase ISO alpha-2/alpha-3 codes are validated.

Domain coordinates are `Coordinate(longitude, latitude)` in WGS84 degrees;
GeoJSON arrays are `[longitude, latitude]`. Routing JSON instead uses
`{latitude, longitude}`, geocoding positions `{lat, lon}`, and the routing path
uses **latitude,longitude** pairs. These orders are explicitly tested.
Meters and seconds stay meters and seconds; no miles/time conversion occurs in
the adapter. Numeric JSON decimals normalize through Decimal/Fraction, then the
existing domain validators reject booleans, nonfinite/negative values and bad
geometry/timing.

## Exact requests and authentication evidence

Official pages read on 2026-10-10:
[TomTom Routing v1 Calculate Route](https://docs.tomtom.com/routing-api/documentation/tomtom-maps/v1/calculate-route),
[Geocoding v1](https://docs.tomtom.com/geocoding-api/documentation/tomtom-maps/v1/geocode),
[Guidance instructions](https://docs.tomtom.com/routing-api/documentation/tomtom-maps/v1/guidance-instructions).
These v1 endpoint parameter tables document required **query `key`**; their
request-header tables do not document an API-key header. A header supported by a
different TomTom product is not evidence for these endpoints. The implementation
uses query authentication with transport tracing suppressed. The exact repeated
extended-representation names also match the approved provider-findings spike;
comma-separated values are not substituted.

Routing: GET `/routing/1/calculateRoute/{lat,lon}:{lat,lon}/json`
(fallback inserts its actual waypoint between the same endpoints).

| Query parameter | Sent value |
|---|---|
| travelMode | truck |
| maxAlternatives | 2 |
| alternativeType | anyRoute |
| routeRepresentation | polyline |
| extendedRouteRepresentation | distance |
| extendedRouteRepresentation, repeated | travelTime |
| traffic | false |
| departAt | submitted departure normalized to UTC ISO8601 with Z |
| key | [REDACTED] |

Geocoding: GET `/search/2/geocode/{URL-encoded sanitized query}.json` with
`limit=5`, `storeResult=false`, `key=[REDACTED]`; `countrySet=US,CAN` only when
explicitly configured. No deprecated `typeahead`, Copyright API, vehicleWeight,
axle weight, truck dimensions or cargo restriction parameters are sent.
Sanitization removes control characters, keeps word separation, trims and
collapses whitespace. D20 labels allow 2..200 characters; D21 lookups require
3..200 after sanitization, so two-character lookups fail before any call.
Candidates preserve provider order and score ties, expose label/coordinate/
region/country/type/score, and use a SHA-256 ID of normalized label, coordinates,
region, country and match type. Maximum five candidates; empty results are valid.

## Sparse timing and truck limitations

Parse `summary.lengthInMeters`, `summary.travelTimeInSeconds`,
`legs[].points[]`, and route-level `progress[]` entries with `pointIndex`,
`distanceInMeters`, `travelTimeInSeconds`. The existing `build_route` validates
index range/order, monotonic distance/time, initial/final vertices, summary
endpoint agreement and geometry-distance reconciliation. It expands sparse
anchors by traveled geometric chainage. There is **no even-spread timing guess**.

Invalid progress may recover only from actually supplied
`guidance.instructions[]` containing `pointIndex`, `routeOffsetInMeters`,
`travelTimeInSeconds` and `point`. Guidance must satisfy all timing validations
and its point must match the indexed geometry vertex within the existing 1m
endpoint tolerance. Official guidance can point inside a segment while its index
precedes that point; this adapter rejects such unmappable guidance rather than
inventing a vertex/time. Valid progress does not require guidance. Existing
domain endpoint tolerances are 1m/1s and geometric allowance is 1% plus5m;
reconciliation warnings/source remain on the Route.

Generic `truck` mode requests provider truck routing. Cargo is **not gross
vehicle weight**; without real tare/axle/dimension inputs the adapter cannot
claim clearance, weight-limit or vehicle-compliance certification. `traffic=false`
means static modeled durations with no live traffic; travel time is not a
guarantee, and ETAs assume continuous driving without fuel/rest stops.

Submitted departure must be timezone-aware and within now−5min..now+7days.
Only a provider rejection specifically indicating a past departure within the
five-minute grace permits one corrected routing request using the injected
current UTC time. Return `ROUTING_DEPARTURE_ADJUSTED`, preserve both timestamps,
and retain **submitted_departure** as the later checkpoint ETA anchor. This
correction is not an automatic transport retry. The smoke disables it to keep
its two-request limit. Auth/quota/no-route and unrelated invalid requests do not
trigger correction.

## Distinctness and bounded fallback

Pure deterministic code is located in providers because domain edits are limited:

| Module | Pure public functions |
|---|---|
| providers/tomtom.py | sanitize_query, parse_candidates, parse_route, parse_routes, fallback_waypoints; private _object, _array, _number, _point, _text, _anchors |
| providers/distinctness.py | point_distance, arc_distance, weighted_samples, directional_overlap, symmetric_overlap, overlap_is_duplicate, distinct_routes; PolylineIndex geometric index; private _dot, _cross, _vector, _angle, _between, _coordinate |
| providers/transport.py | json_object, normalized_error, retry_delay, private _error_flags (pure normalization helpers; the module also contains I/O classes) |
| domain/geometry.py, domain/identity.py | existing chainage/interpolation/build_route validation and stable_route_id, unchanged |

Resample **geometric** route chainage every804.672m (0.5mi), with origin and
destination exactly once. Each sample owns length between adjacent midpoint
boundaries, including half endpoints and the actual final remainder. Matching
uses minor-great-circle point-to-polyline distance **<=100m**. Directional overlap
is matched owned length / total; symmetric overlap is the **maximum** of both
directions. Fraction weights preserve the exact ratio comparison: **>9/10** is
duplicate, exactly9/10 allowed. Canonical geometry IDs sort before filtering;
same-ID variants tie by duration/distance. Keep up to three. An ephemeral 3D
Earth-centered spatial grid works across antimeridian/poles; arcs subdivide to
<=500m for bounding boxes. The .01m box padding covers arc bulge only and never
shifts the 100m matching cutoff. The index is local acceleration, not a stored
provider-result cache. This spherical metric is not independent ellipsoidal
survey evidence near exactly100m.

If fewer than three remain, choose the fastest accepted native route (distance then
canonical order break ties). Interpolate its **provider-calibrated half-distance**
point and use the containing geometry segment's initial geodesic bearing.
Offset that point by **5% of route distance, clamped to1..50km**, at bearing−90°
(left) then bearing+90° (right), on the existing mean-radius sphere. Wrap longitude
to[-180,180). These are **request waypoints**, never returned synthetic geometry.
Make at most two real routing requests through those positions, same endpoints/
truck/options/departure. Accept only provider routes with endpoints within1km
of submitted endpoints, waypoint within100m of the returned polyline and duration
**<=1.5× fastest native duration**, including native near-clones discarded by
canonical filtering. The detour cap is search-only, never ranking.
Distinctness filters all retained/new candidates. Failed, unmatched, duplicate,
over-cap and no-route fallback candidates are discarded; auth/quota failures
stop immediately. Skip remaining fallback when time left<=3s and emit
`FALLBACK_SKIPPED_DEADLINE`; other recoverable failures emit `FALLBACK_UNAVAILABLE`.
One/two accepted routes emit `PARTIAL_ROUTES` with count; zero raises `NO_ROUTE`.
These duration/offset/endpoint/time-reserve choices are documented implementation
conventions within the approved fallback policy, not additional PDF thresholds.

## Reliability, secret handling and absence of storage

Timeouts: connect<=3s, routing read<=25s, geocoding read<=8s, each clamped to the
remaining shared deadline (maximum35s). One geocoding retry is permitted only
for ConnectError or502/503/504, with default backoff .5s (configurable0..0.5).
No timeout/auth/invalid/no-route/429 retry. A valid numeric/date Retry-After is
honored in full only when it fits the remaining budget; it does not create an
unbounded sleep. Routing has no automatic transport retries. Limiter waits,
backoff, fallback, body reads and phase checks use the same deadline.

Two shared worker slots bound outstanding I/O. The caller wait is hard-bounded
even if an injected client ignores timeouts; queued work is cancelled, active
work retains its limiter slot until finished. Synchronous HTTP calls cannot be
forcibly killed; an outstanding call may finish later, and its already-started
request may still count against quota. Parsing/comparison check the deadline
before returning; integrated long-trip35s latency remains the M5 live gate,
not a claim inferred from these synthetic checks. The limiter reserves<=5
starts per half-open rolling second and<=2 concurrent calls, in one process;
separate processes require later operational coordination.

Success bodies must be JSON objects, bounded to32MiB decoded bytes. Error
handling tolerates JSON/XML/empty/misleading content types, extracts only a code
match and a past-rejection boolean, and emits this closed set:

| Code | Exact safe message |
|---|---|
| NO_ROUTE | No route is available for these locations. |
| QUOTA_EXCEEDED | The provider request allowance has been reached. |
| PROVIDER_AUTH | The provider credentials are unavailable or not authorized. |
| PROVIDER_TIMEOUT | The provider operation exceeded its time budget. |
| PROVIDER_UNAVAILABLE | The provider is temporarily unavailable. |
| MALFORMED_PROVIDER_RESPONSE | The provider returned invalid or incomplete data. |
| INVALID_REQUEST | The provider request is invalid. |

401/403 map auth,429 quota,408/504 timeout, recognized NO_ROUTE_FOUND no-route,
400/404/405/414/415/422 invalid, other failures unavailable. Public HTTP status/
envelope mapping is later API work. `as_dict()` contains only code, safe message
and a boolean past_departure_rejected detail. Transport exceptions are replaced
outside their catch blocks so neither cause nor context retains the unsafe
exception. Response bodies/metadata are excluded from reprs, transport repr
redacts credentials, redirects/proxy inheritance are disabled. HTTPX INFO logs
full URLs and httpcore DEBUG may log headers, so their known transport loggers
receive filters suppressing **all** library traces (process-wide impact).
Injected clients must obey the no-request-logging protocol themselves. Application
metrics may report safe status/count/duration only; never raw URLs/headers/bodies.

No geocode/route result cache, persisted response, shared analysis cache, or
recorded live response fixture is created. `storeResult=false` is explicit on
geocoding. Connections and limiter timestamps are operational state, not results.
Tests prove identical operations issue fresh calls. All new offline data are
synthetic; the historical real weather fixtures are not used by this task.
Attribution returns provider TomTom, `confirmed=false`, and the clearly flagged
text **TomTom attribution pending user confirmation of section 17.3.** Exact
copyright content/display permission remains user-owned; no Copyright API call.

## Authorized domain and settings changes

1. `domain/route_policy.py`: default checkpoint_budget300→200 plus explanatory
   comment. Tests include exact200/201 single-route counts. Current interval
   selection still counts **before pooling**; dedupe-aware shared200-location
   budgeting is future corridor/weather integration, not completed here.
2. Sparse model change: **none required**. Existing Route/build_route already
   accepts geometry-indexed sparse timing; model/geometry files are unchanged.

| Setting | Change in settings.py and .env.example |
|---|---|
| ROUTING_READ_TIMEOUT_SECONDS | default/example12→25 |
| PROVIDER_REQUESTS_PER_SECOND | added, default/example5, allowed1..5 |
| PROVIDER_CALL_CONCURRENCY | added, default/example2, allowed1..2 |
| PROVIDER_RETRY_BACKOFF_SECONDS | added, default/example0.5, allowed0..0.5 |
| PROVIDER_ATTEMPTS | value remains2; comment now geocoding-only transient retry, routing correction separate |

Connect3, geocoding8 and analysis35 were already correct and remain unchanged.
All other settings unchanged, including MAX_WEATHER_COORDINATES300: the additional
authorization excludes that weather setting; align it to200 in the weather task.
The later factory must map PROVIDER_ATTEMPTS−1 into geocode_retries and share
limiter/configuration. No real .env is edited. Existing HTTPX0.28.1 is reused;
no dependency/lock/install/audit change. Lint uses the documented repository-root
command, matching CI; Ruff's inferred import grouping differs in a backend cwd.

## Verification commands and remaining work

PowerShell from quoted repository path, without activation:

```powershell
& "./backend/.venv/Scripts/python.exe" -m pytest "./backend/tests"
& "./backend/.venv/Scripts/python.exe" "./dev.py" lint --only backend
& "./backend/.venv/Scripts/python.exe" "./dev.py" build --only backend
```

Strict typing from backend (same paths work in Linux with .venv/bin/python):
`& "./.venv/Scripts/python.exe" -m mypy --strict "domain" "providers"`.
Optional smoke uses ROUTESHIELD_LIVE_TOMTOM=1, configured local key and only
`tests/test_live_tomtom.py -s`; it disables retries, waypoint fallback and past-time
correction. It makes at most one routing request with departAt60s in the past
and one geocoding request, sharing35s. Ordinary tests block socket construction,
connections and DNS. No live response is recorded.

Executed results and the once-only smoke outcome are recorded in
[acceptance-tests.md](acceptance-tests.md). Future work: weather/corridor pooling,
application composition/global quotas/per-IP throttles, API serialization/DST
validation, frontend/maps and integrated/hosted verification. Three distinct
routes are required for full PDF fulfillment; an honest partial response alone
does not meet that requirement. AGENTS.md's phase/default-history paragraphs
need a later documentation update; this task's explicit edit scope excludes it.
