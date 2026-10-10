# RouteShield public API — offline implementation, 2026-10-11

IMPLEMENTED | This milestone joins the approved domain rules and normalized adapters.
No provider call, browser display, release gate, installation, push or deployment
was performed during verification. Tests use explicitly synthetic adapters and the
existing socket blocker. This document does not amend the frozen decisions.

## Endpoints and selection

| Method and path | Behavior |
|---|---|
| POST `/api/v1/route-analysis/` | Selected endpoints → real adapter routes → common interval/mandatory pooling → ETA forecast lookup → risk/aggregation/ranking/explanation; HTTP200 can mean incomplete or blocked |
| GET `/api/v1/geocode/?q=...` | Trimmed3–200-character query; at most five candidate choices; empty matches is200; no automatic selection |
| GET `/api/v1/health/` | Provider/database-independent liveness, `{ "status":"ok", "version":"0.1.0", "check":"liveness" }` |
| GET `/api/v1/health/?ready=1` | Configuration readiness, `{ "status":"ready", "version":"0.1.0", "check":"readiness" }`; not provider/release readiness |

Only documented ordinary methods are accepted (no automatic OPTIONS/HEAD provider
work). Configured CORS preflights separately return200/empty body and no provider
work; they are a header protocol, not a JSON result. Every API response has
`X-Request-ID` and `Cache-Control: no-store`.
CORS exposes `X-Request-ID` and `Retry-After`. Server IDs are generated locally;
client correlation headers are never trusted as IDs. No server route/geocode cache,
analysis-result cache, job storage or persistent database is introduced. Only the
existing successful normalized forecast cache is shared across requests.

Send a SelectedPlace projection, not the entire lookup Candidate object: label,
latitude, longitude, optional candidate_id/provider/attribution. Candidate display
metadata (region/country/match_type/score) is returned by geocoding and is not an
analysis input. Submitted attribution is checked structurally but never trusted as
provider credit, fetched, or echoed. Direct coordinates use identical D20 checks.
No label, provider name or submitted URL chooses a fetch endpoint. Fixed TomTom
URLs and the weather adapter's official forecast-endpoint allowlist remain in force.

Synthetic analysis request:

```json
{
  "origin": {"label":"Synthetic origin","latitude":0,"longitude":0},
  "destination": {"label":"Synthetic destination","latitude":0,"longitude":1},
  "departure_time":"2026-10-11T12:01:00+00:00",
  "departure_timezone":"UTC",
  "load_weight_lb":30000.5,
  "checkpoint_interval_miles":10,
  "simulation_scenario":null
}
```

The example needs a frozen test clock or an updated departure when used later.
Unknown fields, duplicate JSON keys/query parameters, nonstandard JSON constants,
control characters in text and invalid types fail without upstream work. Labels
are trimmed2–200 characters; finite WGS84 coordinates cannot be booleans; endpoints
must differ. Cargo is0–100000lb inclusive; null and numeric strings are rejected.
The optional interval must be an integer10/25/50; explicit null is invalid.
Departure requires an ISO offset and an IANA name that round-trips to the same
wall time/offset. Nonexistent DST wall times fail; either explicitly offset repeated
instant is valid. The inclusive window is now−5minutes through now+7days.
JSON content type is required; declared or bounded-read body length above16384bytes
is rejected before the JSON parser. Invalid JSON has a field-level body error.

## Pipeline, results and availability

One injected service takes geocoder, router, WeatherProvider, shared QuotaLedger,
UTC clock, monotonic clock, Deadline factory and request-ID generator. Views only
parse/dispatch and format safe errors. Production composition creates no HTTP
requests on startup and shares the limiter/ledger/weather cache per process.
Health does not instantiate or require provider adapters.

Routing uses its existing bounded fallback and original submitted departure for
all ETAs. Provider order is sorted by the existing canonical directed geometry ID;
ranking then determines response order and nullable ranks. The longest accepted
route selects the adaptive default, unless an interval was requested. The service
tries that interval and permitted coarser ones against actual100m unique pooling,
retaining all mandatory checkpoints. More than200 pooled points at50mi fails.
The historical conservative sum is not used for this API. Each route's midpoint
ownership remains exact and includes both endpoints. No optional corridor points
or heatmap frames are generated in this milestone.

The shared forecast window starts at floor(departure hour) and ends at
ceil(max(departure+48h,latest ETA)). The enclosing row t owns(t−1h,t]; no nearest
hour, extrapolation or hourly-risk interpolation occurs. Missing observations go
through the actual risk engine with null hazards. Incomplete known No Travel
evidence stays `known_blocked=true`; it can yield BLOCKED with UNKNOWN and null
rank/average. Unknown ownership remains its own partition, never Low. The
known-block mileage diagnostic overlaps UNKNOWN and must not be added to category
miles. Local time/timezone are null when a geographic IANA zone is absent or
invalid; `utc_fallback=true` and `eta_utc` label that case explicitly.

The unchanged domain produces these statuses/messages:

| recommendation_status | message |
|---|---|
| RECOMMENDED | Recommended fully assessed route |
| BEST_FULLY_ASSESSED_AVAILABLE | Best fully assessed available route |
| ALL_BLOCKED | No safe route at this departure time and load |
| NO_FULLY_ASSESSED_TRAVELABLE_ROUTE | No fully assessed travelable route |
| ALL_INCOMPLETE | All routes have incomplete weather data |

`ASSESSED`, `BLOCKED_COMPLETE`, `UNRANKED` are the existing ranking groups.
Route travel statuses remain ASSESSED/BLOCKED/INCOMPLETE. Recommended ID is nullable;
least-blocked ID is a separate complete-data diagnostic. All comparison facts,
decisive criteria and explanation text come from the domain, with no frontend
ranking or classification. The policy_version `D01-D24-2026-10-10` identifies the
approved decision revision, not completion of all its planned features.

Synthetic response **excerpt** (the full closed schema also includes trip, routes,
checkpoint weather/reasons, profiles, attributions and metadata):

```json
{
  "route_count":3,
  "recommendation_status":"RECOMMENDED",
  "message":"Recommended fully assessed route",
  "decisive_criterion":"HIGH_MILES",
  "is_simulation":false,
  "simulation_scenario":null
}
```

The hand-calculated integration fixture has one23mi route with final levels
[Low,Severe,High,Low] and ownership[5,10,6.5,1.5], hence average66/23; another is
uniform Moderate and another uniform High. Moderate wins against High on High
miles and against the first route on Severe miles. Tests inspect actual comparison
facts/text and the exact66/23 result, not a hardcoded recommendation.

Synthetic error example:

```json
{"error":{"code":"LOCATION_REQUIRES_SELECTION","message":"Select a location with coordinates.","details":{"origin":"COORDINATES_REQUIRED"}},"is_simulation":false,"simulation_scenario":null}
```

Geocoding candidates include candidate_id, label, latitude/longitude, nullable
region/country, match_type, exact score, provider and authoritative attribution;
the response also has attribution and the same request metadata. A synthetic
candidate in the tests is `synthetic-place`/`Synthetic selected place` at[0,0].
No-match geocoding returns candidates[] empty with metadata/credit.

## Exact serialization and shared types

- Fraction values use `ExactNumber={numerator:string,denominator:string}` with
  decimal integer strings and positive denominator. Example66/23 is
  `{ "numerator":"66", "denominator":"23" }`. This applies to chainage, mileage,
  durations, averages, coverage, raw comparison values, quota and cache ages.
  There is no silent float conversion, truncation or display rounding of them.
- Decimal cargo/weather/reason thresholds use exact decimal strings, including
  exponent form when supplied as a Decimal. JSON numeric tokens are parsed with
  Decimal; booleans are checked before numeric conversion. The server preserves
  `30000.0000000000000000001`; JS clients must not claim precision their own numeric
  input already lost. Current ordinary numeric input types are unchanged.
- Coordinates are finite JSON numbers using the existing normalized Coordinate
  model. Operational millisecond timings are measured floats; counts and indices
  are integers. These are not ranking inputs. NaN/Infinity are rejected on input
  and serialization; enums use names, including explicit UNKNOWN with no ordinal.
- UTC ISO timestamps end in Z. Checkpoint datetime resolution is one microsecond,
  as in the existing domain; exact elapsed seconds remain available separately.
  A known local timestamp retains its offset and IANA zone; no fixed-offset guess.
- Weather preserves exact source component amounts/original units, normalized
  values/units, forecast interval start/end, fetched_at and provider/model/cache
  provenance. Hourly-average rates refer to liquid/snow accumulation; wind uses
  its forecast row timestamp. A known final risk exposes its existing1–5 ordinal;
  UNKNOWN exposes ordinal=null, never a safe ordinal.
- `schema.py` is the small authoritative hand-maintained schema. Committed
  `frontend/src/api/types.ts` is its deterministic rendering; the offline drift
  gate compares every field/type and mutation tests reject one-sided additions
  and removals. Recursive tests check every endpoint/status/error variant against
  this closed schema. No OpenAPI dependency was added; it remains optional later.

## Errors and warnings

Every error uses `{error:{code,message,details}}`; analysis errors additionally
have simulation identity. Details contain only fixed field names and fixed codes,
never arbitrary submitted keys, locations, exception strings, URLs, raw bodies,
credentials or traceback. A correlation ID is in the response header. Throttling
adds integer `Retry-After` seconds. Health's405 message stays `Use GET.`.

| Error code | HTTP |
|---|---:|
| VALIDATION_ERROR | 400 |
| PAYLOAD_TOO_LARGE | 413 |
| UNSUPPORTED_MEDIA_TYPE | 415 |
| LOCATION_REQUIRES_SELECTION | 422 |
| NO_ROUTE | 422 |
| TRIP_TOO_LARGE | 422 |
| THROTTLED | 429 |
| DEADLINE_EXCEEDED | 504 |
| PROVIDER_TIMEOUT | 504 |
| PROVIDER_UNAVAILABLE | 503 |
| QUOTA_EXCEEDED | 503 |
| PROVIDER_AUTH | 502 |
| MALFORMED_PROVIDER_RESPONSE | 502 |
| INTERNAL_ERROR | 500 |
| METHOD_NOT_ALLOWED | 405 |
| NOT_FOUND | 404 |
| SIMULATION_DISABLED | 400 |
| INVALID_SCENARIO | 400 |

Provider INVALID_REQUEST maps to VALIDATION_ERROR. Before routes exist, exhausted
shared time maps to DEADLINE_EXCEEDED rather than resetting a provider budget.
Typed routing/geocoding failures use the table; routing timeout is never retried
by orchestration. Weather-stage failures retain known routes and return200 with
unavailable samples/warnings. Thus transport200 never certifies a safe trip.

| Warning code | Scope / meaning |
|---|---|
| PARTIAL_ROUTES | trip; fewer than3 real accepted routes |
| INTERVAL_INCREASED | trip; requested/default spacing increased; actual interval in trip |
| INCOMPLETE_WEATHER | route ID; exact coverage_fraction; null average and incomplete eligibility |
| FORECAST_HORIZON_LIMIT | route ID; actual forecast availability excludes an ETA |
| DEMO_QUOTA_REACHED | trip; process ledger refused work; no fabricated weather |
| WEATHER_UNAVAILABLE | trip/route ID; upstream weather outage/quota failure |
| DEADLINE_WEATHER_UNAVAILABLE | trip; weather work could not fit remaining time |
| BLOCKED_TRIP | trip; domain ALL_BLOCKED, including known blocks with incomplete weather |
| UTC_FALLBACK | trip; checkpoint local_time/timezone are null |
| ROUTING_DEPARTURE_ADJUSTED | trip; existing adapter's rejected-past-departure recovery, original ETAs |
| FALLBACK_SKIPPED_DEADLINE | trip; existing adapter bounded search skipped |
| FALLBACK_UNAVAILABLE | trip; existing adapter bounded search failure |

Weather availability codes are unchanged: OUT_OF_HORIZON, MISSING_HOUR,
MISSING_FIELD, PAST_TIME, PROVIDER_FAILURE, QUOTA_EXCEEDED, DEMO_QUOTA_REACHED.
ReasonCode and all domain comparison/explanation/status codes are reused unchanged.
The TomTom attribution stays confirmed=false with its flagged17.3 placeholder;
no Copyright call occurs. Open-Meteo's CC BY4.0 conversion/processing notice and
OpenFreeMap/OpenMapTiles/OpenStreetMap credits are returned. Metadata alone is not
visible map attribution or a release permission. All three release gates stay OPEN.

## Deadline, metadata, logs and protection

An analysis/geocoding RequestContext starts in API middleware before body parsing
and DRF throttling, once lazy process composition is available. Exactly one injected
Deadline is shared with every route fallback and weather batch. The configured
budget is capped at35s. Adapter phase caps remain connect3s, routing<=25s and
geocoding/weather<=8s, bounded by the remaining deadline. No automatic routing
timeout retry occurs. A bounded shared caller executor also limits uncooperative
provider waits and queue time; cancellation does not release an actual in-flight
provider's limiter slot early. Late work cannot become a cached success.

Expired before routes:504. Expired before/during weather: skip pending work and
return200 unavailable/incomplete routes. A completed partial weather result from
the adapter is retained even at deadline, preserving previously obtained known
blocks. If a provider never returns a partial result, the caller constructs
Unavailable(PROVIDER_FAILURE) series. Post-provider risk/serialization completes
locally; a0.5s operational margin is reserved for this bounded completion and
scheduling, not additional upstream work. Real blocked fake tests use a0.05s
deadline and assert caller return before0.55s for routing and weather; fake clocks
prove the35s is never restarted. This is offline evidence, not the TIME-03 live
long-trip performance gate. Lazy construction is configuration/connection-pool
setup without network; it is excluded from service stage timings on the first call.

Metadata reports request_id, service total_ms, per-stage measured milliseconds,
actual send counts (routing/geocoding/weather, including retries/fallback), weather
cache hits/misses/exact ages, successful quota units reserved, effective deadline,
and simulated=false. Reservation totals include a later pre-send refund; they are
not the provider's verified billable counter or shared-ledger before/after delta.
The shared Deadline has locked per-request counters, so concurrency/UTC rollover
cannot contaminate another request's metadata. Synthetic providers record sends
explicitly; a protocol fake that makes no HTTP send has no implicit upstream count.
generated_at/expires_at are snapshot metadata, not a route cache; expiry uses the
oldest series fetch time plus the approved15min freshness period. Per-stage times
cover validation, routing, checkpoints_and_pooling, weather, risk_and_aggregation,
ranking_and_explanation (or geocoding); total includes parsing and intervening work
through result construction. The single structured log also observes HTTP rendering.

One structured `routeshield.requests` record contains request_id, route_name,
status, total_ms, stage_ms and provider_calls. It excludes URLs, headers, labels,
addresses, coordinates, bodies and exception text. Its explicit INFO console
handler emits JSON without propagation/duplicate parent output. Django's request
and development-server path loggers are suppressed; HTTPX suppression remains
in adapters. The test checks INFO is enabled without changing the runtime level.
Production reverse-proxy/server access-log privacy still needs hosting review.

Existing environment settings ANALYSIS_RATE_LIMIT=10 and
ANALYSIS_RATE_WINDOW_SECONDS=600, GEOCODE_RATE_LIMIT=30 and
GEOCODE_RATE_WINDOW_SECONDS=60 now drive DRF throttles. Scope and hashed client IP
keys are separate; LocMem read/modify/write is locked within the process. The
daily QuotaLedger is also shared across IPs with the existing8000-unit default.
These controls are best-effort per process/reset on restart, not distributed.
Throttles are friction, **not a DoS defense**.

New API_TRUSTED_PROXY_CIDRS is a comma-separated server environment setting;
default empty trusts no proxy and ignores forged X-Forwarded-For. Example reserved
documentation CIDR `192.0.2.0/24` illustrates syntax, not a hosting recommendation.
Configure only the actual controlled proxy CIDRs on hosting; it must overwrite or
correctly append that header. With a trusted immediate peer, walk the chain from
the right through trusted hops and choose the first untrusted address; malformed
headers use the peer, and oversized headers are ignored. Never trust0.0.0.0/0.
The setting is documented here because this task did not authorize editing
backend/.env.example. No real environment file was created or changed.

Strict mypy checks the API/service/schema/validation code. Approved DRF lacks a
py.typed marker/stubs: narrowly documented import/base-class ignores contain that
framework boundary; no new dependency or broad mypy exclusion is introduced.

## PROPOSED CHANGE to architecture.md — user approval still pending

| ID | Difference implemented under this task's explicit instructions |
|---|---|
| API-P01 | Interim analysis omits corridor/49frames/truck_positions/capabilities until the next heatmap task; keeps midpoint risk_profile. This is not completion of the final frozen public contract. |
| API-P02 | Use this task's closed error inventory/statuses: INVALID_INPUT→VALIDATION_ERROR400; NO_ROUTE404→422; TRIP_TOO_LARGE400→422; REQUEST_LIMIT→THROTTLED429; ANALYSIS_TIMEOUT→DEADLINE_EXCEEDED504; PROVIDER_INVALID_RESPONSE/ROUTE_TIMING_UNAVAILABLE→MALFORMED_PROVIDER_RESPONSE502; PROVIDER_FAILURE→PROVIDER_UNAVAILABLE503, explicit PROVIDER_TIMEOUT504/PROVIDER_AUTH502/QUOTA_EXCEEDED503. DST issues are field details on VALIDATION_ERROR400. Body/media/selection/method/endpoint failures gain explicit typed codes. |
| API-P03 | QUOTA-02's429 DEMO_QUOTA_REACHED is superseded for an analysis with known routes by the explicitly requested200, unavailable checkpoints, ALL_INCOMPLETE (or preserved known-block evidence) and DEMO_QUOTA_REACHED warning. Throttle alone is429; typed routing/geocode provider-quota failure is503. |
| API-P04 | Simulation remains deferred: documented preset selections fail SIMULATION_DISABLED400, with explicit attempted true/preset identity; unknown selections fail INVALID_SCENARIO400 (unknown attempted ID is not echoed). No SIMULATION_ENABLED behavior or simulated weather is implemented yet. Pre-parse size/media errors cannot identify a scenario and carry false/null. |
| API-P05 | Specify lossless ratio/decimal-string serialization, null local_time/timezone with utc_fallback, and the expanded injected request metadata/schema dictionary below; no client reranking. |

No edit to architecture.md, decisions.md, the frozen contract or AGENTS.md was made.
These are proposals to align those planning documents with this authorized milestone;
they are not new user approvals or release-gate resolutions.

## Added name inventory and scoped wiring

Public error names newly introduced relative to architecture's example table:
VALIDATION_ERROR, PAYLOAD_TOO_LARGE, UNSUPPORTED_MEDIA_TYPE,
LOCATION_REQUIRES_SELECTION (already D20), THROTTLED, DEADLINE_EXCEEDED,
PROVIDER_TIMEOUT, QUOTA_EXCEEDED, PROVIDER_AUTH, MALFORMED_PROVIDER_RESPONSE
(last four reuse provider error vocabulary), METHOD_NOT_ALLOWED (existing health),
NOT_FOUND. NO_ROUTE/INTERNAL_ERROR/PROVIDER_UNAVAILABLE/SIMULATION_DISABLED/
INVALID_SCENARIO retain existing names; statuses/proposed renames are above.
The complete public warning inventory is above: newly specified API warning names
are INTERVAL_INCREASED, INCOMPLETE_WEATHER, FORECAST_HORIZON_LIMIT,
WEATHER_UNAVAILABLE, DEADLINE_WEATHER_UNAVAILABLE, BLOCKED_TRIP, UTC_FALLBACK.
PARTIAL_ROUTES/DEMO_QUOTA_REACHED and the three adapter fallback/departure codes
reuse approved or implemented vocabulary.

Fixed public validation-detail names used here: INVALID_JSON, EXPECTED_OBJECT,
UNKNOWN_FIELDS, INVALID_LENGTH_OR_TYPE, CONTROL_CHARACTER, EXPECTED_NUMBER,
NON_FINITE_VALUE, OUT_OF_RANGE, COORDINATES_REQUIRED, INVALID_TYPE,
INVALID_SCENARIO, DISABLED, IDENTICAL_ENDPOINTS, INVALID_INTERVAL,
INVALID_IANA_ZONE, OFFSET_REQUIRED, INVALID_DATETIME,
ZONE_OFFSET_MISMATCH_OR_NONEXISTENT, OUTSIDE_DEPARTURE_WINDOW,
INVALID_CONTENT_LENGTH, DUPLICATE_FIELDS. Reused names are not new risk rules.
Other new public names/fields/types are exhaustively enumerated in the dictionary
below. New operational names: API_TRUSTED_PROXY_CIDRS, routeshield.requests,
POLICY_VERSION value D01-D24-2026-10-10, COMPLETION_MARGIN_SECONDS=0.5,
RequestContext and AnalysisService. They introduce no provider, library or ranking rule.

Domain changes: candidate_intervals() offers adaptive/common permitted intervals
without conservative counting; generate_checkpoints(...,check_budget=False) allows
an API caller to enforce the actual unique cap after pooling. Default behavior is
unchanged for existing callers. Provider wiring changes only: Deadline gains locked
record_call()/record_reservation()/metrics(); TomTomTransport records an actual
send immediately before HTTPClient.get; WeatherTransport records successful quota
reservations and actual sends. No provider request, parsing, retry, unit, quota,
cache or threshold policy was changed. No dependency was added.

## Field dictionary

Each table row below is the authoritative schema object's complete field/type map.
`?` means optional; all other fields are required. Arrays are ordered. Position is
[longitude,latitude]. Record keys in summary.miles_by_level are the five known
RiskLevel names; UNKNOWN is represented by unknown_miles separately. FactValue is
an exact ratio, string, count number, boolean or null. Explanations are server facts.

| Type | Fields (name: type) |
|---|---|
| ExactNumber | `numerator`: `string`; `denominator`: `string` |
| Attribution | `provider`: `string`; `text`: `string`; `confirmed`: `boolean`; `source_url`: `string \| null`; `licence_url`: `string \| null` |
| SelectedPlace | `label`: `string`; `latitude`: `number`; `longitude`: `number`; `candidate_id?`: `string`; `provider?`: `string`; `attribution?`: `Attribution` |
| AnalysisRequest | `origin`: `SelectedPlace`; `destination`: `SelectedPlace`; `departure_time`: `string`; `departure_timezone`: `string`; `load_weight_lb`: `number`; `checkpoint_interval_miles?`: `10 \| 25 \| 50`; `simulation_scenario?`: `string \| null` |
| HealthResponse | `status`: `"ok" \| "ready"`; `version`: `string`; `check`: `"liveness" \| "readiness"` |
| ErrorDetail | `code`: `ErrorCode`; `message`: `string`; `details`: `Record<string, string>` |
| ErrorResponse | `error`: `ErrorDetail`; `is_simulation?`: `boolean`; `simulation_scenario?`: `string \| null` |
| Warning | `code`: `string`; `message`: `string`; `scope`: `string`; `coverage_fraction`: `ExactNumber \| null` |
| ProviderCalls | `routing`: `number`; `geocoding`: `number`; `weather`: `number` |
| CacheDiagnostics | `hits`: `number`; `misses`: `number`; `ages_seconds`: `ExactNumber[]` |
| Metadata | `request_id`: `string`; `total_ms`: `number`; `stage_ms`: `Record<string, number>`; `provider_calls`: `ProviderCalls`; `weather_cache`: `CacheDiagnostics`; `quota_units_reserved`: `ExactNumber`; `deadline_seconds`: `number`; `simulated`: `boolean` |
| Candidate | `candidate_id`: `string`; `label`: `string`; `latitude`: `number`; `longitude`: `number`; `region`: `string \| null`; `country`: `string \| null`; `match_type`: `string`; `score`: `ExactNumber`; `provider`: `string`; `attribution`: `Attribution` |
| GeocodeResponse | `candidates`: `Candidate[]`; `attribution`: `Attribution`; `metadata`: `Metadata` |
| Trip | `origin`: `SelectedPlace`; `destination`: `SelectedPlace`; `departure_time`: `string`; `departure_timezone`: `string`; `load_weight_lb`: `string`; `reference_time`: `string`; `requested_interval_miles`: `number \| null`; `effective_interval_miles`: `number` |
| RiskBand | `level`: `RiskLevel`; `printed_pdf_band`: `string`; `lower`: `string \| null`; `upper`: `string \| null`; `lower_inclusive`: `boolean`; `upper_inclusive`: `boolean` |
| RiskReason | `code`: `ReasonCode`; `metric`: `string`; `measured_value`: `string \| null`; `band`: `RiskBand \| null`; `threshold`: `string \| null`; `comparison`: `string \| null`; `level`: `RiskLevel`; `wind_mph`: `string \| null`; `load_weight_lb`: `string \| null` |
| RiskResult | `wind_risk`: `RiskLevel`; `rain_risk`: `RiskLevel`; `snow_risk`: `RiskLevel`; `hazard_risk`: `RiskLevel`; `load_adjusted_wind_risk`: `RiskLevel`; `final_risk`: `RiskLevel`; `known_risk_floor`: `RiskLevel \| null`; `known_blocked`: `boolean`; `ordinal`: `number \| null`; `reasons`: `RiskReason[]` |
| WeatherValues | `wind_mph`: `string \| null`; `rain_in_hr`: `string \| null`; `snow_in_hr`: `string \| null`; `gust_mph`: `string \| null` |
| WeatherSource | `components`: `Record<string, NullableExactNumber>`; `units`: `Record<string, NullableString>`; `hourly_average_rates`: `boolean` |
| Weather | `values`: `WeatherValues`; `source`: `WeatherSource \| null`; `units`: `Record<string, string>`; `forecast_timestamp`: `string`; `interval_start`: `string`; `interval_end`: `string`; `fetched_at`: `string`; `provider`: `string`; `model`: `string`; `cache_hit`: `boolean`; `unavailable_reason`: `UnavailableReason \| null`; `missing_fields`: `string[]`; `hourly_average_rates`: `boolean` |
| Checkpoint | `id`: `string`; `index`: `number`; `mile_marker`: `ExactNumber`; `owned_miles`: `ExactNumber`; `elapsed_seconds`: `ExactNumber`; `coordinate`: `Position`; `eta_utc`: `string`; `local_time`: `string \| null`; `timezone`: `string \| null`; `utc_fallback`: `boolean`; `weather`: `Weather`; `risk`: `RiskResult` |
| RiskProfileSegment | `start_mile`: `ExactNumber`; `end_mile`: `ExactNumber`; `final_risk`: `RiskLevel`; `known_risk_floor`: `RiskLevel \| null`; `known_blocked`: `boolean`; `checkpoint_id`: `string` |
| RouteSummary | `total_miles`: `ExactNumber`; `total_duration_s`: `ExactNumber`; `miles_by_level`: `Record<string, ExactNumber>`; `unknown_miles`: `ExactNumber`; `average_risk`: `ExactNumber \| null`; `known_only_average_risk_diagnostic`: `ExactNumber \| null`; `maximum_known_level`: `RiskLevel \| null`; `known_risk_floor`: `RiskLevel \| null`; `no_travel_checkpoint_count`: `number`; `no_travel_miles`: `ExactNumber`; `known_blocked_checkpoint_count`: `number`; `known_blocked_miles_diagnostic`: `ExactNumber`; `known_blocked`: `boolean`; `coverage_fraction`: `ExactNumber`; `travel_status`: `TravelStatus` |
| CriterionValues | `no_travel_miles`: `ExactNumber`; `severe_miles`: `ExactNumber`; `high_miles`: `ExactNumber`; `average_risk`: `ExactNumber \| null`; `duration_seconds`: `ExactNumber`; `stable_route_id`: `string` |
| Route | `route_id`: `string`; `geometry`: `Position[]`; `distance_m`: `ExactNumber`; `duration_s`: `ExactNumber`; `profile`: `string`; `live_traffic`: `boolean`; `attribution`: `Attribution`; `travel_status`: `TravelStatus`; `rank`: `number \| null`; `group`: `string`; `criteria`: `CriterionValues`; `checkpoints`: `Checkpoint[]`; `summary`: `RouteSummary`; `risk_profile`: `RiskProfileSegment[]` |
| ComparisonFact | `winner_route_id`: `string`; `other_route_id`: `string`; `criterion`: `string`; `winner_value`: `FactValue`; `other_value`: `FactValue`; `code`: `string` |
| ExplanationFact | `code`: `string`; `route_id`: `string \| null`; `other_route_id`: `string \| null`; `values`: `Record<string, FactValue>` |
| AnalysisResponse | `analysis_id`: `string`; `policy_version`: `string`; `generated_at`: `string`; `expires_at`: `string`; `trip`: `Trip`; `routes`: `Route[]`; `route_count`: `number`; `recommended_route_id`: `string \| null`; `least_blocked_route_id`: `string \| null`; `recommendation_status`: `RecommendationStatus`; `message`: `string`; `decisive_criterion`: `string`; `diagnostic_decisive_criterion`: `string \| null`; `explanation`: `string`; `comparison_facts`: `ComparisonFact[]`; `explanation_facts`: `ExplanationFact[]`; `is_simulation`: `boolean`; `simulation_scenario`: `string \| null`; `warnings`: `Warning[]`; `attributions`: `Attribution[]`; `metadata`: `Metadata` |

| Alias | Type |
|---|---|
| Position | `[number, number]` |
| RiskLevel | `"LOW" \| "MODERATE" \| "HIGH" \| "SEVERE" \| "NO_TRAVEL" \| "UNKNOWN"` |
| TravelStatus | `"ASSESSED" \| "BLOCKED" \| "INCOMPLETE"` |
| RecommendationStatus | `"RECOMMENDED" \| "BEST_FULLY_ASSESSED_AVAILABLE" \| "ALL_BLOCKED" \| "NO_FULLY_ASSESSED_TRAVELABLE_ROUTE" \| "ALL_INCOMPLETE"` |
| UnavailableReason | `"OUT_OF_HORIZON" \| "MISSING_HOUR" \| "MISSING_FIELD" \| "PAST_TIME" \| "PROVIDER_FAILURE" \| "QUOTA_EXCEEDED" \| "DEMO_QUOTA_REACHED"` |
| ReasonCode | `"HAZARD_CLASSIFIED" \| "MISSING_HAZARD" \| "EXTREME_WIND_ANY_LOAD" \| "SEVERE_WIND_HEAVY_LOAD" \| "HIGH_WIND_HEAVY_LOAD" \| "LOAD_RULES_UNAVAILABLE_MISSING_WIND" \| "LOAD_RULES_UNAVAILABLE_MISSING_LOAD" \| "MISSING_LOAD"` |
| ErrorCode | `"VALIDATION_ERROR" \| "PAYLOAD_TOO_LARGE" \| "UNSUPPORTED_MEDIA_TYPE" \| "LOCATION_REQUIRES_SELECTION" \| "NO_ROUTE" \| "TRIP_TOO_LARGE" \| "THROTTLED" \| "DEADLINE_EXCEEDED" \| "PROVIDER_TIMEOUT" \| "PROVIDER_UNAVAILABLE" \| "QUOTA_EXCEEDED" \| "PROVIDER_AUTH" \| "MALFORMED_PROVIDER_RESPONSE" \| "INTERNAL_ERROR" \| "METHOD_NOT_ALLOWED" \| "NOT_FOUND" \| "SIMULATION_DISABLED" \| "INVALID_SCENARIO"` |
| FactValue | `ExactNumber \| string \| number \| boolean \| null` |
| NullableExactNumber | `ExactNumber \| null` |
| NullableString | `string \| null` |
