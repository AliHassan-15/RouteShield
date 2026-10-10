# Real-provider feasibility findings — 2026-10-10

**CURRENT POLICY NOTICE (2026-10-10):** The user reviewed this spike:200 pooled coordinates (not proposed100/historical300), variable/window/model accounting/default8000 daily guard, routing<=25s within35s/no routing-timeout retry, explicit UTC departAt/traffic=false with past-rejection exception, synthetic-only later offline tests/no server route-geocode cache, conditional attribution and safe error normalization are now approved in [decisions.md](decisions.md). Three OPEN RELEASE GATES remain owned by user; agents never resolve them. This file preserves original spike observations/proposals; it does not establish a release grant.

**VERIFIED:** Scope: throwaway probes and documentation only. No application code, dependency installation, remote operation, provider switch or frozen-contract edit occurred. Existing local HTTPX/Playwright were used. The user authorized reading OpenFreeMap/OSM official documentation and subsequently approved **synthetic TomTom fixtures** in place of stored real results.

**VERIFIED:** Labels distinguish observed responses, published documentation and offline calculations. **UNVERIFIED** identifies absent measurements, unresolved permissions and proposed release behavior. A successful request is not proof of licensing, billing-plan identity or future availability.

## Historical spike verdicts before the provider amendments

| Provider | Verdict | Evidence and limits |
|---|---|---|
| TomTom Routing + Geocoding | **NO-GO for release under the unchanged contract; technical access gate passed** | **VERIFIED:** three distinct truck routes and usable timing on all corridors. **UNVERIFIED:** account-specific free-plan eligibility, public-demo/non-TomTom-map permissions and result-storage rights. **VERIFIED:** both cross-country routing observations exceed the approved 12 s read timeout; the first also exceeds the 35 s total deadline. |
| Open-Meteo | **GO WITH FALLBACK**, conditional on free-service eligibility and cap approval | **VERIFIED:** batching, requested units and observed best-match horizon work. Proposed fallback: reduce pooled coordinates to 100, preserving mandatory checkpoints first; reject trips still over budget at 50 miles. **UNVERIFIED:** public hiring-demo eligibility and proposed policy approval. Null/model gaps must remain UNKNOWN, without synthetic live replacements. |
| OpenFreeMap | **GO** for the documented basemap choice | **VERIFIED (documentation):** commercial use, attribution and free public access are documented. **UNVERIFIED:** actual tile rendering/cache headers; no map/API probe was authorized or performed. |
| OpenStreetMap | **GO WITH FALLBACK** as licensed data / conditional raster fallback | **VERIFIED (documentation):** ODbL and visible attribution; standard tile service has separate cache/fair-use rules. **UNVERIFIED:** actual fallback tile access and operational reliability. |
| openrouteservice | **NO-GO as a general long-haul alternative provider** | **VERIFIED (documentation):** alternative routes capped at 100 km. **UNVERIFIED:** live HGV/plan access and operative terms; no API call or switch was made. |

**VERIFIED:** Native routes passed distinctness, so waypoint fallback was not triggered: **0 extra requests, 0 added measured latency**. **UNVERIFIED:** a future D09 waypoint fallback would cost up to two routing requests; its latency/success were not measured. ORS fallback has zero measured requests/latency because it was not invoked, rather than being an instant replacement.

## Request accounting and reproducibility

| API | Budget reservations / attempts | Completed HTTP responses | Results |
|---|---:|---:|---|
| TomTom | **18 / 40** | **17** | **VERIFIED:** 14×200, 1×401, 2×400; one connection failure |
| Open-Meteo | **11 / 25** | **10** | **VERIFIED:** 10×200; one connection failure |
| ORS / OpenFreeMap / OSM APIs | **0** | **0** | **VERIFIED:** documentation only |

**VERIFIED:** `scripts/spikes/evidence/requests.json` reserves each attempt before sending and records provider, label, UTC time, status, elapsed request seconds, bytes and selected **response** metadata. Connection failures count conservatively against the budget; their on-wire HTTP/charged status is **UNVERIFIED**. The quota caps were interpreted as API calls, excluding non-billable documentation fetches and browser assets. Retained metadata from the final full documentation-browser run records 42 TomTom and 44 Open-Meteo assets; the terms-only run records 42 TomTom, 2 OpenFreeMap and 35 HeiGIT assets. An earlier full browser run and separate web-tool retrievals also occurred; their combined transport total is **UNVERIFIED**, not an API-quota claim.

**VERIFIED:** These PowerShell commands ran from `D:/Projects New/RouteShield`, using the existing explicit interpreter; all executable/script paths were quoted:

```powershell
& 'backend/.venv/Scripts/python.exe' 'scripts/spikes/route_probe.py' urban
& 'backend/.venv/Scripts/python.exe' 'scripts/spikes/route_probe.py' urban --repeat
& 'backend/.venv/Scripts/python.exe' 'scripts/spikes/route_probe.py' medium
& 'backend/.venv/Scripts/python.exe' 'scripts/spikes/route_probe.py' medium --repeat
& 'backend/.venv/Scripts/python.exe' 'scripts/spikes/route_probe.py' long
& 'backend/.venv/Scripts/python.exe' 'scripts/spikes/route_probe.py' long --repeat
& 'backend/.venv/Scripts/python.exe' 'scripts/spikes/route_probe.py' urban --fixed
& 'backend/.venv/Scripts/python.exe' 'scripts/spikes/route_probe.py' urban --fixed --car
& 'backend/.venv/Scripts/python.exe' 'scripts/spikes/weather_probe.py' 50
& 'backend/.venv/Scripts/python.exe' 'scripts/spikes/weather_probe.py' 100
& 'backend/.venv/Scripts/python.exe' 'scripts/spikes/weather_probe.py' horizon
& 'backend/.venv/Scripts/python.exe' 'scripts/spikes/weather_probe.py' analysis
& 'backend/.venv/Scripts/python.exe' 'scripts/spikes/weather_probe.py' missing
```

**VERIFIED:** `geocode_probe.py` ran separately with `ambiguous`, `autocomplete`, `partial`, `misspelled`, `region`, `empty`, `invalid_key`, `no_route` and `disconnected`. `route_analysis.py`, `weather_analysis.py`, `coordinate_budget.py`, `compact_evidence.py`, `fixture_builder.py` and `metric_checks.py` ran offline. Documentation rendering ran with `& 'C:/Program Files/nodejs/node.exe' 'scripts/spikes/docs_browser.mjs'` and `terms_probe.mjs`; official links below were also inspected with the web tool. Failed connection attempts were retried explicitly, never by an automatic uncounted retry.

**VERIFIED:** The pricing calculator screenshot was visually inspected: four variables, three days, one requested model and 300 locations displayed **300.0 API calls**. The bulky screenshot/raw payloads were temporary and removed before commit; compact evidence retains the inputs/result. Offline analyses originally used those raw inputs, so their historical commands do not imply those inputs remain available. Future raw TomTom recording requires storage permission; see `scripts/spikes/README.md`.

## A. TomTom routing

**VERIFIED (live):** First probes used `maxAlternatives=2`, `alternativeType=anyRoute`, `travelMode=truck`, `routeRepresentation=polyline`, repeated `extendedRouteRepresentation=distance` and `extendedRouteRepresentation=travelTime`. No parameter was rejected. `traffic=false` was explicit; departure defaulted to request time. The fixed truck/car comparison additionally used `departAt=2026-10-11T12:00:00Z`. No cargo weight, axle weight or dimensions were invented. **UNVERIFIED:** comma-separated extended representation was unnecessary and not tested.

| Corridor; public endpoints | Returned route distances (miles) | First / repeat HTTP seconds | Status/routes |
|---|---|---|---|
| Santa Monica Pier → Los Angeles City Hall | 17.106 / 28.266 / 30.503 | **2.472 / 2.634** | **VERIFIED:** 200; 3 / 3 |
| Chicago → Detroit | 284.814 / 305.388 / 334.990 | **6.256 / 3.792** | **VERIFIED:** 200; 3 / 3 |
| Los Angeles City Hall → New York City Hall | 2,812.674 / 2,801.487 / 3,019.136 | **52.149 / 14.749** | **VERIFIED:** 200; 3 / 3 |

**VERIFIED:** The urban primary is under 30 miles; its longest alternative is slightly above 30. Latencies include fresh HTTP client, connection/TLS and complete body reading. **UNVERIFIED:** provider cache state; “first/repeat” is not a controlled cold-server experiment. Probe read timeout was 60 s to observe behavior; production timeout settings were not changed.

**VERIFIED (offline):** D09 metric used 0.5-mile haversine chainage sampling with midpoint/half-endpoint ownership, 100 m sample-to-polyline tolerance, symmetric **maximum** directional coverage and rejection strictly above 0.90. Point-to-segment distance uses a local tangent-plane approximation on the fine provider segments. Stable geometry hashes determine filtering order. All nine pairs pass; repeats have the same overlap despite changing timing anchors.

| Trip; zero-based provider pair | A covered by B | B covered by A | Symmetric maximum |
|---|---:|---:|---:|
| Urban 0–1 | .356209 | .225973 | **.356209** |
| Urban 0–2 | .326945 | .180432 | **.326945** |
| Urban 1–2 | .155257 | .147649 | **.155257** |
| Medium 0–1 | .138306 | .129261 | **.138306** |
| Medium 0–2 | .263163 | .221388 | **.263163** |
| Medium 1–2 | .034153 | .030097 | **.034153** |
| Long 0–1 | .032914 | .033010 | **.033010** |
| Long 0–2 | .004428 | .004104 | **.004428** |
| Long 1–2 | .004412 | .004270 | **.004412** |

**VERIFIED:** Eight offline controls pass, including identical/duplicate routes, vertex-density independence, directional containment, a parallel route beyond tolerance, owned-length conservation and the strict cutoff. **UNVERIFIED:** independent geodesic-library validation near exactly 100 m; these observed pairs are far from the rejection threshold.

| First-response trip | Geometry vertex counts | Sparse progress counts | Timing validation |
|---|---|---|---|
| Urban | 567 / 880 / 947 | 24 / 37 / 28 | **VERIFIED:** usable on all three |
| Medium | 4,517 / 5,036 / 5,406 | 50 / 62 / 59 | **VERIFIED:** usable on all three |
| Long | 38,694 / 34,954 / 39,957 | 289 / 284 / 324 | **VERIFIED:** usable on all three |

**VERIFIED (live + offline):** JSON geometry is `legs[].points[]` with WGS84 latitude/longitude objects. Summaries use `lengthInMeters` and `travelTimeInSeconds`; route-level `progress[]` supplies `pointIndex`, `distanceInMeters`, `travelTimeInSeconds`. Arrays are **not equal in length**. Each starts at vertex 0/distance 0/time 0, ends at the final vertex, is monotonic in all three fields and ends at the exact summary distance/time. Example long primary: 38,694 vertices vs 289 anchors, ending at index 38,693, distance 4,526,560 m and time 142,367 s. Expanding between anchors by geometry chainage yields one monotonic value per vertex with no gaps and the same endpoint values. This is provider timing interpolation, not whole-route uniform speed.

**VERIFIED (documentation):** Sparse progress is supported; `maxAlternatives` accepts 0–5 and fewer alternatives may be returned. [Calculate Route](https://docs.tomtom.com/routing-api/documentation/tomtom-maps/v1/calculate-route). **UNVERIFIED:** a universal alternatives distance cap; none was established from that page. The observed maximum returned route was 4,858.828 km, which is an empirical success rather than a contractual limit.

**VERIFIED (live):** At the same fixed departure, truck primary took **1,553 s** versus car **1,473 s**, with identical 27,530 m/567-vertex primary geometry. Truck alternatives were 49,090/45,489 m; car alternatives 45,370/49,106 m. Thus profile affects timing and some alternatives. **UNVERIFIED:** specific truck clearances or gross-weight compliance, because those specifications were deliberately omitted.

**VERIFIED (documentation):** Published free allowance is 20,000 routing and 20,000 geocoding requests/month; default routing/geocoding limit is 5 QPS. [Pricing](https://docs.tomtom.com/pricing), [QPS limits](https://docs.tomtom.com/platform/documentation/api-best-practices/qps-limits). **UNVERIFIED:** this key's subscribed plan, actual charged usage and load-tested limits; responses provided no usage/rate counters. No quota was deliberately exhausted.

## B. Open-Meteo weather and budget

**VERIFIED (live):** Every weather probe requested `hourly=wind_speed_10m,rain,showers,snowfall`, `wind_speed_unit=mph`, `precipitation_unit=inch`, `timezone=UTC`, `timeformat=unixtime`. Returned metadata consistently was:

```json
{"time":"unixtime","wind_speed_10m":"mp/h","rain":"inch","showers":"inch","snowfall":"inch"}
```

**VERIFIED (documentation):** `wind_speed_10m` is non-gust wind at 10 m, sampled at the hour; rain/showers/snowfall are preceding-hour accumulations. Snowfall is snow depth, separate from snow-water equivalent. [Hourly variable semantics](https://open-meteo.com/en/docs). **UNVERIFIED:** a particular meteorological averaging period for the wind prediction; it must not be described as a measured gust or a certified sustained-wind observation.

**VERIFIED (offline normalization under D03/D05):** Accept metadata `mp/h` as mph. For row t owning `(t−1h,t]`, liquid rate = `(rain_inches + showers_inches) / 1 hour`; snow rate = `snowfall_depth_inches / 1 hour`. Inch numeric values therefore remain unchanged except liquid addition. If SI responses are explicitly accepted later, rain/showers mm divide by 25.4 and snow depth cm divides by 2.54 before division by one hour. No snowfall water-equivalent factor is applied. ETA 12:20 uses 13:00; exact 13:00 uses 13:00. Unknown/missing inputs do not become zero.

| Real response example, UTC | Raw wind / rain / showers / snow | Normalized wind mph / liquid in/hr / snow in/hr | Hazard level |
|---|---|---|---|
| 50-location sample, Oct 10 15:00 | .5 / 0 / 0 / 0 | .5 / 0 / 0 | **VERIFIED:** LOW |
| 50-location sample, Oct 11 12:00 | 14.6 / .197 / 0 / 0 | 14.6 / .197 / 0 | **VERIFIED:** MODERATE |
| 50-location sample, Oct 11 11:00 | 7.1 / .327 / 0 / 0 | 7.1 / .327 / 0 | **VERIFIED:** HIGH |
| 50-location sample, Oct 11 16:00 | 7.8 / .539 / 0 / 0 | 7.8 / .539 / 0 | **VERIFIED:** SEVERE |
| 100-location sample, Oct 11 19:00 | 10.4 / 1.205 / 0 / 0 | 10.4 / 1.205 / 0 | **VERIFIED:** NO_TRAVEL |
| 16-day sample, Oct 14 01:00 | 15.5 / 1.504 / .079 / 0 | 15.5 / 1.583 / 0 | **VERIFIED:** NO_TRAVEL; showers included |

**VERIFIED:** Across the observed samples, wind reached 40.3 mph (HIGH), snow depth rate .11 in/hr (LOW), and liquid rain reached all five bands. Exactly **25.0 mph** was observed at Oct 10 22:00 UTC and classifies MODERATE. No other exact decision boundary was observed. These are hazard-level results; no load was supplied, so they do not demonstrate load-adjusted final risk. Every sampled threshold occurrence is recorded in `weather_analysis.json`; exhaustive boundary/load tests remain later domain work.

| Live probe | Location count / hourly rows per location | HTTP seconds | Result |
|---|---|---:|---|
| 48-hour batch | 50 / 49 inclusive timestamps | **1.342** | **VERIFIED:** 200, one location object per coordinate |
| 48-hour batch | 100 / 49 | **2.521** | **VERIFIED:** 200 |
| Best-match 16 days | 50 / 384 | **1.499** | **VERIFIED:** 200, no null required fields |
| Uncached analysis | 300 / 50, six batches of 50 | **11.249 serial sum** | **VERIFIED:** six 200s; 611,732 bytes total |
| ICON-global 16 days | 2 / 384 | **1.037** | **VERIFIED:** 200 with null forecast tail |

**VERIFIED:** All time steps were 3,600 seconds. Successful 100-location batching proves at least that size, not a maximum. **UNVERIFIED:** the provider's absolute coordinate maximum and two-concurrent-batch latency; requests here were sequential to preserve simple budget accounting. D21's production limit of 50/batch was not changed.

**VERIFIED:** Best-match `forecast_days=16` returned **2026-10-10T00:00:00Z through 2026-10-25T23:00:00Z**, all four required fields non-null at the 50 sampled locations. At the horizon probe's reference **2026-10-10T15:42:45Z**, now+7 departure is Oct 17 15:42:45, and its slider end is **Oct 19 15:42:45Z** (enclosing row 16:00). Longest observed route duration was 154,045 s / 42 h 47 m 25 s on the repeat, less than 48 hours, so its latest ETA also fits this observed window. **UNVERIFIED:** all future coordinates/models/trips; timestamps alone are not evidence of valid data.

**VERIFIED:** The actual 300-coordinate probe used real route-corridor samples, default `best_match`, all four variables and UTC **Oct 10 15:00 → Oct 12 16:00**, including both enclosing endpoints, with six uncached 50-coordinate requests. The selected coordinates were spread across the full native-route pool for quota testing; they were not a production mandatory-checkpoint selection. Individual batch seconds were **1.264, 1.276, 2.066, 2.446, 2.487, 1.710**. No usage/quota headers were returned on any successful weather response.

**VERIFIED (published accounting + rendered calculator):** Four variables, <14 days, one requested model and 300 coordinates cost **300 quota units**, although sent as six HTTP requests. Two 50-coordinate batches would cost 100 units, without reducing the required variables/window. The calculator accepts days rather than hours; three calendar days cover the measured 50-hour window, within the no-time-surcharge band. [Accounting and calculator](https://open-meteo.com/en/pricing). **UNVERIFIED:** actual charged account/IP counter; none was exposed. The underlying automatic model mix was not returned as usage metadata.

**UNVERIFIED — PROPOSED:** Reduce the pooled analysis cap from 300 to **100**, a 66.7% reduction in maximum corridor coordinates and roughly threefold spacing on an equal-length corridor, before accounting for mandatory points. **VERIFIED:** Using approved geometry chainage and 100 m point deduplication, the observed long routes require **58 / 57 / 62 checkpoints, 173 unique pooled points**, even at 50-mile spacing. A cap of 100 cannot cover this trip; D04's existing trip-too-large policy would reject it. Do not silently omit required checkpoints or use a fourth interval. With the current 300 cap, this example leaves 127 slots for optional corridor density; with 100, none are available and mandatory points still exceed the cap.

**VERIFIED:** Best-match probes did not omit a required variable. The explicit ICON-global probe had **191 null tail hours per variable per location**; timestamps still continued to Oct 25 23:00. The real null fixture includes the last valid row and first two null rows. Missing-field absence in a live response is **UNVERIFIED**, while a real null case is verified. Its normalized state must be UNKNOWN, without interpolation/extrapolation or model substitution presented as live data.

## C. Geocoding and error observations

**VERIFIED (live):** Geocoding returned `summary`, `results[]`, `type`, `score`, structured `address` and `position.lat/lon`. With `countrySet=US&limit=5`, ambiguous “Springfield” returned Missouri, Illinois, Massachusetts, Virginia and Oregon in decreasing scores (2.5415 → 2.4222). The region request using lat 42.10/lon −72.59/radius 50,000 m made Massachusetts first and reduced total candidates from 99 to 6. All returned candidates were US places. [Geocode parameters](https://docs.tomtom.com/geocoding-api/documentation/tomtom-maps/v1/geocode).

**VERIFIED (documentation):** Bounding boxes via `topLeft`/`btmRight` and a result limit up to 100 are also documented. **UNVERIFIED:** live bounding-box enforcement and maximum-limit behavior; only country/radius restrictions and limit 5 were tested.

**VERIFIED (live):** “350 Fift Avnue New York” returned corrected 5th Avenue candidates, with Brooklyn and Manhattan tied at 9.314859; Brooklyn came first. A top score/tie is not proof of the intended address. “Springf” returned fuzzy matches headed by Colorado Springs rather than Springfield. `typeahead=true` and the same request without it both returned 200 and identical candidate ordering. **VERIFIED (documentation):** that parameter is deprecated. **UNVERIFIED:** dependable prefix-autocomplete semantics; retain explicit candidate selection and a debounced geocode lookup rather than promising a dedicated suggestion service.

| Probe | Status / result | Seconds |
|---|---|---:|
| Ambiguous / deprecated typeahead / plain partial | **VERIFIED:** 200 / five candidates each | 1.681 / 1.137 / 1.296 |
| Misspelled / region-constrained | **VERIFIED:** 200 / five candidates each | 1.668 / 1.040 |
| Nonsense address | **VERIFIED:** 200, `results=[]`, totalResults 0 | 1.171 |
| Deliberately invalid placeholder key | **VERIFIED:** 401, `detailedError.code=Unauthorized` | 1.159 |
| Ocean origin | **VERIFIED:** 400, `MAP_MATCHING_FAILURE` | 1.417 |
| Honolulu road network → Los Angeles | **VERIFIED:** 400, `NO_ROUTE_FOUND` | 2.309 |
| Account quota exceeded | **UNVERIFIED (live):** not induced; documented 429 only | not measured |

**VERIFIED:** Observed error responses were JSON. **VERIFIED (documentation):** authentication/quota failures may instead return XML regardless of the requested JSON route format. [Route errors](https://docs.tomtom.com/routing-api/documentation/tomtom-maps/v1/calculate-route), [quota status](https://docs.tomtom.com/platform/documentation/status-and-support/faqs). **UNVERIFIED:** a live XML/429 body; synthetic quota fixture deliberately leaves body null.

## D. Terms, attribution and storage

**VERIFIED:** Browser rendering recovered 52,703 characters of operative TomTom terms; the web extractor still returned only the shell. The clauses were read, not copied wholesale into the repository. [TomTom agreement](https://docs.tomtom.com/legal/terms-and-conditions).

| Provider/source | Verified published position | Still unverified |
|---|---|---|
| [TomTom agreement](https://docs.tomtom.com/legal/terms-and-conditions) | **VERIFIED:** §2.1 ties the solution grant to an accepted subscription; §2.2 covers evaluation. §11.4 restricts result storage to cache-header conditions; §17.3 requires generated attribution or Copyright API integration. | **UNVERIFIED:** this account's grant for a public hiring demo, non-TomTom basemap display, permanent fixtures and exact generated attribution. Live routing headers were `no-cache, no-transform`; geocode responses had no cache-control header. No Copyright API call was authorized/made. |
| [TomTom FAQ](https://docs.tomtom.com/platform/documentation/status-and-support/faqs) / [pass-through terms](https://www.tomtom.com/en-gb/legal/third-party-product-terms/) | **VERIFIED:** FAQ says commercial applications can be built in free evaluation; §11.5 incorporates additional restrictions. | **UNVERIFIED:** reconciliation with the account agreement, pass-through EULA and this demo's use. Do not treat FAQ wording as fixture-storage permission. |
| [Open-Meteo terms](https://open-meteo.com/en/terms) / [licence](https://open-meteo.com/en/licence) | **VERIFIED:** free service is non-commercial; private/educational examples allowed, promotional/commercial activities excluded. Data CC BY 4.0 allows storage/redistribution/adaptation with credit, licence link and change notice, with Open-Meteo linked next to displayed location data. Service has no availability guarantee. | **UNVERIFIED:** whether this public hiring-assessment demo is non-commercial. Data licence does not override free-endpoint eligibility. |
| [OpenFreeMap](https://openfreemap.org/) / [terms](https://openfreemap.org/tos/) | **VERIFIED:** commercial use and free public maps allowed, no SLA; preserve OpenMapTiles and OpenStreetMap credits (OpenFreeMap credit optional). Project MIT is separate from OSM data licensing. Terms prohibit unauthorized automated collection. | **UNVERIFIED:** blanket bulk/offline tile caching permission or HTTP cache rules; none was measured. Normal MapLibre attribution must remain visible, including in video. |
| [OSM copyright](https://www.openstreetmap.org/copyright) / [tile policy](https://operations.osmfoundation.org/policies/tiles/) | **VERIFIED:** data ODbL, including commercial use, attribution and applicable database share-alike. Raster service requires visible OSM credit, normal browser identification/referrer and cache-header compliance (at least seven days if headers cannot be read); no bulk/prefetch downloading. | **UNVERIFIED:** actual tile headers/access. OSMF raster-server rules are not automatically OpenFreeMap's vector-server rules. |
| [ORS restrictions](https://openrouteservice.org/restrictions/) / [operative terms](https://account.heigit.org/info/tos) | **VERIFIED:** official terms link redirected to HeiGIT; both web extraction and restricted browser produced HTTP 200 but no readable clauses. Alternatives limit is 100 km. | **UNVERIFIED:** commercial/demo grant, exact attribution, caching/storage and account quotas. No API/account operation occurred. |

**VERIFIED:** Open-Meteo's published free limits are 600 units/minute, 5,000/hour, 10,000/day and 300,000/month. [Pricing](https://open-meteo.com/en/pricing). **UNVERIFIED:** exact enforcement at equality, existing shared-IP usage and remaining allowance; the global quota guard must use conservative published accounting.

**UNVERIFIED — questions to resolve before release (not a provider switch authorization):**

1. For the accepted TomTom account plan, do §2.1/§2.2 and the free-evaluation FAQ permit this public hiring demo and displaying route/geocode results over OpenFreeMap, after the §11.5 pass-through conditions? Confirm the applicable grant rather than assuming the general page resolves it.
2. Does TomTom permit permanent test recordings or session display despite §11.4 and the observed cache headers, and what Copyright API output must be shown under §17.3? Synthetic fixtures are approved only for this spike; real recordings remain incomplete.
3. Does Open-Meteo classify this publicly hosted assessment demo as permitted non-commercial use under its Non-Commercial Use section, rather than excluded promotional activity? Free-only remains binding if the answer is no.

## Surprises

- **VERIFIED:** Extended progress is sparse rather than one value per geometry vertex; usable first/last anchors prevent this from being a timing-access gate failure.
- **VERIFIED:** Cross-country first/repeat calls took 52.149/14.749 s, both beyond the approved routing read timeout; the first was also beyond the full analysis deadline.
- **VERIFIED:** A 300-location analysis costs 300 published units despite only six HTTP calls. Lowering the cap to 100 would reject the observed 173-checkpoint long trip.
- **VERIFIED:** Returned wind unit is `mp/h`, not the request spelling `mph`; model-dependent null tails can coexist with a full 16-day timestamp array.
- **VERIFIED:** Deprecated `typeahead=true` still accepted 200 but did not produce reliable Springfield prefix matches. Misspelling correction can produce equally scored different municipalities.
- **VERIFIED:** TomTom terms are readable in a browser; unresolved storage permission prompted user-approved synthetic fixtures. The precise public-demo grant remains **UNVERIFIED**.

## Historical proposed decision / frozen-contract changes — superseded by user decisions

1. **UNVERIFIED — PROPOSED D04/D09:** Treat `progress[]` as validated sparse geometry-indexed cumulative anchors; interpolate between them by geometry chainage. Remove the assumption that extended arrays must equal vertex count. **VERIFIED evidence:** all 24 returned routes have valid monotonic endpoints; all expand without gaps.
2. **UNVERIFIED — PROPOSED D03/D05:** Accept documented units plus the observed `mp/h` alias; validate metadata/array lengths and all required values. Keep enclosing-hour ownership, rain+showers and snow depth; consider model horizon valid only where values exist. **VERIFIED evidence:** real units and ICON null fixture; no threshold changes.
3. **UNVERIFIED — PROPOSED D10/D20/D21:** Cap pooled coordinates at **100**, keep 50/batch and mandatory checkpoints first, coarsen optional heatmap samples and disclose density; fail clearly if 50-mile mandatory checkpoints still exceed 100. **VERIFIED evidence:** 300 calculator units, 173 mandatory long-trip points; tradeoff is reduced long-haul coverage, not just visual density. Approval is required before orchestration.
4. **UNVERIFIED — PROPOSED D21/D23:** Keep the 35 s global deadline but allow routing read time up to 25 s within that deadline, bounded by remaining time; do not automatically repeat expensive routing timeouts. Long calls exceeding the total still fail explicitly. **VERIFIED evidence:** observed 14.749 s repeat would fit that per-call limit; 52.149 s first would not. **UNVERIFIED:** integrated latency and global-deadline success rates; no promise of cross-country coverage.
5. **UNVERIFIED — PROPOSED D09/D21:** Explicit departure timestamp and traffic policy in routing requests; debounce ordinary geocode candidate lookup, avoid deprecated typeahead, require candidate selection. **VERIFIED evidence:** fixed-mode timing difference, fuzzy partial behavior and misspelled-address score tie. No new search provider/API is proposed.
6. **UNVERIFIED — PROPOSED D11/D16:** Extend the current-task synthetic-fixture approach to later offline tests pending recording permission; keep route/geocode persistence disabled, and resolve release/licence questions above before integration/display. **VERIFIED evidence:** user approved synthetic replacements; terms/browser/header observations are recorded.
7. **UNVERIFIED — PROPOSED D11/D13:** Define required TomTom Copyright API attribution alongside OpenMapTiles/OSM and location-adjacent Open-Meteo credit. Add future Copyright API authorization only after the applicable display grant is confirmed. **VERIFIED evidence:** §17.3 and each provider's linked attribution instructions; exact TomTom generated content remains unmeasured.
8. **UNVERIFIED — PROPOSED D09/D23:** Normalize provider status/content type and tolerate JSON, XML or empty quota/auth errors before mapping to the frozen public `{error:{code,message,details}}` shape. **VERIFIED evidence:** live 401/400 codes, documented XML possibility; no client stack traces/key-bearing URLs. Public endpoints and risk/ranking policies stay as frozen.

## Fixtures, verification and remaining work

**VERIFIED:** `backend/tests/fixtures/providers/` contains six explicitly synthetic TomTom fixtures: three-route response, geocode, empty geocode, invalid-key 401, no-route 400 and quota 429. User approved the replacement on 2026-10-10. No real geometry/address result is represented as a recording. Two real, trimmed Open-Meteo fixtures cover batching and null-tail values; their README supplies provenance and CC BY attribution.

**UNVERIFIED:** Live quota body, permanent real TomTom fixture permission, ORS operative licence and all release questions remain incomplete. Conditional waypoint fallback was correctly skipped because no tested trip needed it. Missing variable absence was not observed; real null weather was observed. No production adapters, domain implementation, UI/provider integration or provider switch was developed.

**VERIFIED:** Final verification is recorded in `scripts/spikes/evidence/verification.json`: Python compilation, compact-script limits, fixture structure, eight overlap controls, request-budget/accounting consistency, approved file scope and exact-key/key-pattern scans. Final Ruff check passes; both browser scripts pass `node --check`. Initial lint findings were corrected before staging. Application tests/type-check/build and live application/browser flows were skipped because application files were unchanged; provider documentation was rendered in a real local browser.

**VERIFIED:** Before the one authorized commit, the staged-file review ran `verify_files.py --staged`, `tools/check_staged.py`, `git diff --cached --check`, and inspected the staged file list/stat. It found no actual key, key-like credential assignment, private key, `.env`, PDF or ignored artifact, and confirmed no changes to `AGENTS.md` or `docs/decisions.md`. The local commit message is `docs: provider feasibility findings`; no remote or push was requested/performed.

**HISTORICAL:** At spike completion these proposals were unapplied. User decisions dated2026-10-10 now approve1/2/6/7/8 and modify3/4/5; current choices are in decisions.md. The original measured values/proposal text are preserved as evidence, not current policy. Non-display development may proceed only in a focused authorized task; the three user-owned release gates remain OPEN.
