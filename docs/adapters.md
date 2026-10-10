# Provider adapters

The routing/geocoding sections record the 2026-10-10 TomTom milestone under
D09/D11/D13/D19/D20/D21. That milestone added no weather implementation. The
2026-10-11 weather implementation is recorded below. Neither milestone builds
an API endpoint or frontend. All three user-owned release gates in decisions.md
remain OPEN; technical access and non-display development do not settle them.

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
authorization excluded that weather setting. The weather milestone below now
aligns its default and effective upper bound to200; the real .env is untouched.
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
[acceptance-tests.md](acceptance-tests.md). Weather/corridor pooling and the process
quota ledger are implemented below. Future work: application composition/per-IP throttles, API serialization/DST
validation, frontend/maps and integrated/hosted verification. Three distinct
routes are required for full PDF fulfillment; an honest partial response alone
does not meet that requirement. AGENTS.md's phase/default-history paragraphs
need a later documentation update; this task's explicit edit scope excludes it.

## Weather adapter milestone — 2026-10-11

IMPLEMENTED | `WeatherProvider.fetch(pooled_coordinates, window, deadline=...)`
returns `WeatherResult.series` in precisely the input order. Each immutable
`WeatherSeries` holds the requested whole UTC hours and either `HourlyWeather`
or typed `Unavailable` at every requested hour. Successful hours retain exact
source components/raw units, normalized Decimal values and provenance: provider,
requested model selection, fetched-at UTC epoch and cache-hit flag. Provenance
does not invent which underlying model supplied automatic `best_match` data.
Mappings are read-only. These normalized types live in providers/contracts.py;
domain code and the frozen contract were not edited.

`OpenMeteoWeather.from_mapping(PROVIDER_CONFIG, client=..., clock=..., sleeper=...,
limiter=..., ledger=..., cache=...)` consumes prepared environment settings
without importing Django. Inject one shared clock-aware quota ledger, limiter,
weather cache and adapter per process, and pass the SAME Deadline through future
routing/weather orchestration. Creating new ledgers per analysis would bypass
the process budget. Call adapter.close() and client.close() at lifecycle shutdown.
No HTTP is performed during construction. There is no route/geocode caching.

### Exact forecast request and hour ownership

GET the environment-driven Open-Meteo forecast endpoint, default
`https://api.open-meteo.com/v1/forecast`, without a key. Parameters are:

| Parameter | Exact convention |
|---|---|
| latitude / longitude | Separate comma-separated lists in the pooled input order, <=50 each |
| hourly | wind_speed_10m,rain,showers,snowfall |
| wind_speed_unit / precipitation_unit | mph / inch |
| timeformat / timezone | unixtime / UTC |
| start_hour / end_hour | UTC yyyy-MM-ddTHH:mm, inclusive whole-hour endpoints |
| models | Omitted for automatic best_match; the configured single selector otherwise |
| Optional gusts | Append wind_gusts_10m only when enabled; fifth variable remains within the <=10-variable base charge |

`forecast_window` floors departure to the preceding whole UTC hour and ceilings
max(departure+48h, last checkpoint ETA). `lookup_forecast` selects row t owning
(t-3600,t]: 12:20 ->13:00, exact13:00 ->13:00, 13:00:01 ->14:00. The same row's
instantaneous sustained 10m wind is used; no interpolation, nearest endpoint,
calm fallback or horizon extrapolation. Lookup reports the ETA and selected row
as separate epoch instants and rejects past ETAs as PAST_TIME. An adapter request
is clipped at the documented maximum16-day calendar envelope; this is an upper
request bound, never evidence of valid values. Requested hours outside real
returned coverage stay OUT_OF_HORIZON; null rows remain MISSING_HOUR even when
their timestamps exist. Array lengths must match sorted unique epoch timestamps.

The [official forecast documentation](https://open-meteo.com/en/docs) defines
offset-free start_hour/end_hour. A one-coordinate probe using offset-bearing
hour strings with timezone=auto returned HTTP400. It consumed one request/one
coordinate and is preserved only as numeric status evidence. UTC requests avoid
local-hour reinterpretation and non-whole-hour offset ambiguity. Returned IANA
metadata/offset are retained solely for display; IANA rules handle DST, never a
single fixed offset across the trip. Because this request mode returns UTC/GMT,
the adapter flags an explicit geographic-timezone fallback. A geographic local
zone is not inferred from UTC metadata. Later UI must label this fallback; local
zone enrichment is not implemented in this task. Synthetic New York DST tests
prove lookup stays UTC when genuine IANA display metadata is available.

### Unit and missing-data semantics

The documentation describes rain/showers/snowfall as preceding-hour accumulations,
and wind_speed_10m as instantaneous sustained wind. One-hour liquid average rate
is (rain_inches + showers_inches)/1h; snow average rate is snowfall_DEPTH_inches/1h.
Units are checked separately even though mph/inch were requested. Supported wind
spellings: mph, observed mp/h, km/h, m/s, kn/knots; depth spellings: inch/in, mm, cm.
km/h divides by1.609344; m/s multiplies by2.2369362921; mm divides by25.4; cm divides
by2.54; kn/knots multiplies by1.150779448. No total precipitation, snow-water
equivalent or hidden7:1 factor is used. Optional gusts never replace sustained wind.
Snow depth is not liquid-equivalent precipitation. All rates are explicitly
marked hourly averages rather than instantaneous rain/snow rates.

JSON decimal tokens and source components use Decimal/Fraction; rain+showers is
added exactly before conversion to a Decimal. Defensive non-terminating unit
conversions use a fixed60-digit Context independent of ambient precision/rounding.
No epsilon, risk-band rounding or category interpolation is applied. Source
components and raw units survive for diagnostics, including unknown unit metadata;
unknown units, booleans, strings, negative and non-finite values are unavailable.

Unavailable codes are OUT_OF_HORIZON, MISSING_HOUR, MISSING_FIELD, PAST_TIME,
PROVIDER_FAILURE, QUOTA_EXCEEDED and DEMO_QUOTA_REACHED. Missing showers invalidates
liquid rainfall; it is not assumed zero. Any required missing/invalid component
prevents a complete `HourlyWeather` and prevents successful caching. Consistent
with frozen D08, explicit `Unavailable.known_values` retains the OTHER known
hazards (e.g. wind55 with missing showers) for later known-block/floor calculation.
The property-style tests assert no complete sample when any required input is
missing, and no value for the affected normalized hazard; they deliberately do
not erase known No Travel evidence. No risk classification is added here.

### Measured model coverage

Measured at reference2026-10-10T19:01:45.127170Z, three public city coordinates
(Los Angeles34.0522,-118.2437; Denver39.7392,-104.9903; New York40.7128,-74.0060;
latitude,longitude order).
Each selector fetched UTC Oct10 19:00 -> Oct21 20:00. Ordinary assessment:
Oct10 19:00 -> Oct12 20:00 (50 rows). Longest required assessment:
Oct17 19:00 -> Oct21 20:00 (98 rows), covering departure about seven days out
plus a trip lasting roughly four days. Table counts apply independently at EACH
of the three coordinates; they count numeric non-null values, not timestamps.

| Requested selection | HTTP | Seconds | Ordinary wind/rain/showers/snow | Days7-11 wind/rain/showers/snow | All-required longest rows |
|---|---:|---:|---|---|---:|
| best_match (automatic) |200|1.322|50/50 for each|98/98 for each|98/98|
| icon_global |200|0.368|50/50 for each|6/98 for each|6/98|
| gfs_seamless |200|0.824|50/50 for each|98/98 for each|98/98|

Default remains measured **best_match**: automatic selection ties GFS on full
usable coverage and does not require overriding the approved automatic default.
This is not a forecast-quality comparison or a promise about future locations,
model runs or charged model counts. All returned wind metadata was mp/h and
rain/showers/snow was inch. ICON-global's92 null tail rows are unusable despite
continuing timestamps. Numeric evidence is in weather_model_measurement.json;
the failed hour-format probe is weather_timezone_measurement.json. No raw live
payload was recorded, and these evidence files are not offline weather fixtures.

### Pooling, density, batching and failure isolation

`pool_coordinates` sorts mandatory points by (route id, checkpoint index,
longitude, latitude), then optional points by the same stable key. The first
representative serves subsequent points at great-circle distance <=100m using
the existing domain Earth radius. It is representative-based, not transitive
clustering. A point near two representatives uses the earliest. All mandatory
representatives precede optional coordinates. Every tagged original gets a
pooled index, distance to its representative and coarsened flag.

Optional samples use the same increasing index stride on each sorted route,
retaining endpoint candidates, until their deduplicated pool fits. If even that
minimum cannot fit, optional-only sampling is suppressed uniformly and disclosed;
mandatory points still cover the routes. Unselected optional points map to the
nearest retained representative and are explicitly approximate/coarsened. They
must NEVER replace mandatory checkpoint weather. Report original/selected optional
counts, stride and per-route maximum retained spacing (supplied route chainage,
or a clearly labeled great-circle gap when chainage is absent); zero with fewer
than two retained optional points means no measurable optional spacing. The
OPTIONAL_COORDINATES_COARSENED warning requires later UI disclosure.

The cap is checked AFTER mandatory deduplication. More than200 mandatory pooled
points raises existing `domain.route_types.RouteError` with TRIP_TOO_LARGE before
HTTP. Caller interval escalation through10/25/50 belongs to future orchestration;
no required point is omitted and no fourth interval is invented. The synthetic
long-trip shape uses measured counts58/57/62 (177 originals), shared endpoints
deduplicating to173, and450 invented optional samples coarsened within200. It
copies no TomTom geometry and does not claim those synthetic coordinates are
real route checkpoints.

Input order supplies mandatory-first batches of <=50 with at most two batch
workers and two transport workers; one shared ProviderLimiter bounds actual starts
to5/rolling second and at most2 outstanding calls, including retries. Queued work,
HTTP phases, Retry-After and body processing all consume the shared Deadline.
Only a failed batch's coordinates become unavailable; valid neighbors survive.
`failed_indices` also identifies partial individual series, not just failed HTTP.
The distinct-value fixtures prove location results map back to the correct route
and checkpoint. A worker that outlives the caller deadline keeps its limiter slot
until it really finishes, cannot cache a late success, and queued work is cancelled.

### Exact quota reservations, reliability and weather-only cache

[Published accounting](https://open-meteo.com/en/pricing) is modeled conservatively:

`units = coordinates × max(1, variables/10) × max(1, inclusive_UTC_calendar_days/14) × requested_model_count`.

Calendar days cover the actual upstream start/end hours, inclusive. Every batch
and permitted retry reserves exact Fraction units atomically BEFORE HTTP; equality
at the daily/request guard is allowed. Four variables/three days/one requested
model/300 coordinates ->300 units, matching the recorded pricing calculator.
Automatic best_match counts as ONE requested selection; hidden model mixture and
actual charged counters remain unverified. A model selector is a single name.

Default daily stop8000 and per-upstream-attempt guard200 are independent of HTTP
request count. Exhaustion returns DEMO_QUOTA_REACHED without calling upstream.
A pre-send failure releases the reservation; any HTTP invocation retains its
charge even on connection failure, HTTP failure or timeout, because failures are
not known to be free. Retries reserve again. A queued reservation crossing UTC
midnight rechecks and charges the actual send day. The ledger resets on process
restart and UTC calendar-day rollover, is shared across callers/IPs ONLY inside
that process, and is best effort rather than distributed/provider-counter control.
It does not establish compliance with separate provider minute/hour/month limits.

Connect<=3s/read<=8s and all waits are bounded by remaining Deadline<=35s. At most
one retry for connection failure/502/503/504 uses <=0.5s configured base backoff;
Retry-After may require a longer wait only if the shared deadline can fit it, and
never reduces the base backoff. No invalid/auth/429/read-timeout retry. HTTP429
maps to QUOTA_EXCEEDED for its batch. JSON/XML/empty errors reuse the closed safe
ProviderError set; upstream URLs, queries and bodies are never copied into
messages, logs or exception chains. Native client has no redirects/proxy inheritance
and bounds ephemeral response bytes; no raw response persistence is introduced.

Cache only COMPLETE normalized required-hour series, TTL<=900s, keyed by provider,
requested model, endpoint source, exact coordinate, exact requested window,
variables and request units/timeformat/timezone. Partial/failure series never enter
the cache. A good coordinate may be cached when an unrelated coordinate fails.
Results expose per-operation hit/miss counts, original fetched-at and per-series
ages; hits update series/hour provenance without changing stored weather. Expiry
at900s is a miss; held older payloads can independently be marked stale via
series_is_stale. Bounded capacity defaults400 entries. No route/geocode result cache
exists; no risk/load-specific cache or heatmap payload is built here.

### Every weather setting changed or added

All are optional locally; configured values must satisfy the adapter's approved
bounds. Existing connect3, read8, batch50, concurrency2, TTL900 and provider limiter
settings retain their values. No real .env, routing setting or secret is changed.

| Environment setting | Default / change | Purpose |
|---|---|---|
| MAX_WEATHER_COORDINATES |300 ->200; effective min(configured,200)|Approved unique pooled cap; legacy local300 cannot expand it|
| OPEN_METEO_BASE_URL |https://api.open-meteo.com/v1/forecast|Eligible environment-selected HTTPS endpoint without query/credentials|
| OPEN_METEO_MODEL |best_match|Measured requested model selector|
| WEATHER_ATTEMPTS |2|At most one permitted retry|
| WEATHER_RETRY_BACKOFF_SECONDS |0.5|Positive environment base wait<=0.5s|
| WEATHER_DAILY_QUOTA_UNITS |8000|In-process shared daily UTC stop|
| WEATHER_REQUEST_UNIT_LIMIT |200|Per-upstream-attempt cost guard|
| WEATHER_CACHE_MAX_ENTRIES |400|Bound complete-series cache capacity|
| WEATHER_GUSTS_ENABLED |false|Optional display-only fifth variable, unchanged base charging|
| WEATHER_CACHE_TTL_SECONDS |900 (new PROVIDER_CONFIG wiring; value unchanged)|Weather-series TTL<=15min|

Attribution metadata credits Open-Meteo data under
[CC BY4.0](https://open-meteo.com/en/licence) and says data were converted/processed
for RouteShield. The metadata's confirmed flag confirms this documented DATA
credit, not permission to use the free HOSTED SERVICE for a public assessment.
RG-OPENMETEO-ELIGIBILITY remains OPEN and owned by the user; both TomTom release
gates also remain OPEN. No provider switch, purchase or release decision is made.

The optional `tests/test_live_weather.py` is skipped without
ROUTESHIELD_LIVE_OPEN_METEO=1. It restricts the URL to the forecast endpoint,
disables retries, requests one50-coordinate batch and a disjoint100-coordinate
operation split into two concurrent batches, and uses a future48h/49-row UTC
window. Normal tests keep the socket blocker active. Only numeric coverage/status/
latency/timestamp evidence is recorded; raw payloads and bulk coordinates are
not printed or written. This task's once-only outcome and exact live budget are
recorded in acceptance-tests.md after execution. Do not rerun that task's smoke.

EXECUTED | Once-only smoke passed:50-coordinate operation1.820s;100-coordinate
operation0.666s, two concurrent batches. All three statuses200; all required
variables non-null at every49-row coordinate (2450 and4900 coordinate-hours).
Each request took1.757/0.317/0.576s; no retry or cache hit. Total task usage,
including model coverage and rejected hour-format probe:7 HTTP requests/160
coordinate submissions, below12/250. Numeric smoke evidence contains exact epoch
window endpoints. It does not establish the later integrated35s M5 gate.

Remaining work: API composition/error serialization/per-IP throttles, domain risk
and recommendation integration, heatmap49-frame payload/density disclosure,
geographic local-time display enrichment, frontend/map/browser flow, integrated
long-trip35s M5 evidence, CI execution and hosting. No new dependency was needed;
the dependency audit is skipped because installed dependencies are unchanged.
