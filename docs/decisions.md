# RouteShield decisions and frozen contract

## Frozen contract (approval date: 2026-10-10)

1. Authority: `Requirements/fs-assessment-spotter.pdf`, then these APPROVED/CHANGED decisions; no application is implemented by this document.
2. Routing/geocoding: TomTom truck mode, up to three distinct routes, cumulative distance/time; <=2 real waypoint fallback calls. ORS HGV fallback has a 100 km alternatives cap; STOP for user direction if TomTom's live gate fails.
3. Weather/map/hosts: Open-Meteo; MapLibre GL JS + OpenFreeMap; Cloudflare Pages + Render Free. Only free plans without a required card; conditional alternatives must pass access/license gates.
4. Backend: Python 3.12+, Django, DRF, dataclasses, HTTPX, django-cors-headers, Gunicorn/WhiteNoise on Linux; pytest/pytest-django, Ruff, mypy/django-stubs.
5. Frontend: React + strict TypeScript, Vite, plain CSS, TanStack Query/local state; Vitest/Testing Library, ESLint/tsc, Playwright. No UI/chart/motion library; dependencies pass D19.
6. Wind mph: Low <25; Moderate [25,35); High [35,45); Severe [45,55); No Travel >=55. Use sustained 10 m wind, no rounding or gust escalation.
7. Rain in/hr: Low <.10; Moderate [.10,.25); High [.25,.50); Severe [.50,1.00]; No Travel >1.00.
8. Snow-depth in/hr: Low <.5; Moderate [.5,1); High [1,2); Severe [2,3]; No Travel >3.
9. Load: wind [45,55) and >30000 lb -> No Travel; [35,45) and >40000 lb -> Severe; >=55 blocks any load. Independent hazards, hazard max, adjusted wind, final max retained.
10. Rain = rain + showers; snowfall = depth, never water equivalent. Validate metadata, convert lengths to inches and divide accumulation by hours; explicitly request mph/inch.
11. Forecast row t owns (t-1h,t]; ETA 12:20 ->13:00, exactly13:00 ->13:00; expose wind timestamp. Missing/out-of-horizon is unavailable, never extrapolated.
12. Checkpoints: origin/destination plus 10/25/50 miles along provider-calibrated geometry; common adaptive default by longest route <=100:10, <=500:25, else50; warn on cap-driven increase, fail if50 cannot fit.
13. ETAs interpolate valid provider cumulative timing; UTC internally, validated input offset/IANA zone, checkpoint-local display with explicit UTC fallback; no invented uniform-speed or rest model.
14. Miles: midpoint ownership, endpoints own half-neighbor segments; exact category totals disjoint. Average = unrounded sum(owned miles * ordinal1..5)/route miles for complete routes.
15. Ranking: complete nonblocked first, then Severe miles, High miles, average, duration, canonical ID. Complete blocked compare No Travel miles first then those criteria.
16. Known No Travel always blocks; all blocked -> recommended_route_id=null and separate least_blocked_route_id when complete diagnostics exist, with explicit warning.
17. UNKNOWN never means Low: unknown miles/coverage and known hazard floor retained; incomplete routes shown but unranked/ineligible; full-route average=null.
18. Heatmap: all routes' corridor, h0..48 from departure, 49 backend-classified constant-hue categorical frames; ETA analysis stays fixed; one cached browser payload, zero scrub/play/filter requests.
19. D10: user-started play/pause, never autoplay, reduced motion; selected-route truck marker precomputed from checkpoint ETAs; combined/wind/rain/snow filter only if hazard codes fit <=500 KB compressed.
20. D21: 10 analyses/10min/IP; geocode30/min/IP plus global guard; <=300 locations, <=50/batch, <=2 concurrent, <=1 transient retry, 35s warm deadline, successful weather TTL<=15min.
21. First feasibility spike measures one uncached 300-coordinate Open-Meteo analysis; >100 quota units -> propose a lower cap and obtain direction BEFORE API orchestration; measurement is currently UNVERIFIED.
22. D22: system/manual light-dark theme, CSS variables, refined system typography; optional self-hosted variable font only within size budgets; restrained motion/reduced motion/no layout shift and distance-risk SVG; P2 cuts at missed gates.
23. D24: live default; config-disableable deterministic weather presets: All clear, High-wind corridor, Winter storm, Heavy rain front, Blocked trip, Tie-break; same adapter interface and real risk/aggregation/ranking.
24. Simulation: no silent live/sim mix, real routing in the app; every simulated analysis response has is_simulation=true and simulation_scenario; persistent SIMULATION banner/scenario badge; isolated caches and labeled deterministic browser fixtures.
25. POST /api/v1/route-analysis/: origin/destination Place, departure_time(offset), departure_timezone(IANA), load_weight_lb, optional checkpoint_interval_miles and simulation_scenario (absent/null means live).
26. Success: identity/freshness/trip, routes/geometry/checkpoints/weather/all risk layers/summaries/risk_profile, nullable recommended and least_blocked IDs, explanation/facts/warnings/attributions, is_simulation/simulation_scenario, corridor points/49 frames/ETA-derived truck_positions and capabilities.hazard_filter.
27. GET /api/v1/geocode/?q=: Place candidates; GET /api/v1/health/: provider-independent liveness with version/status/check; ?ready=1 is process/configuration readiness only. Errors: {error:{code,message,details}} with safe statuses and simulation identity on simulated analysis errors.
28. Budgets: <=500 KB compressed analysis, initial JS<=200 KB gzip excluding lazy map, scrub p95<=16.7ms/no sustained>50ms work; report real measurements. No keepalive pings.
29. Delivery: 4 calendar days/16 working hours; elapsed time supplied by user; usable API7h, local journey10.5h, hosted13.75h. Planning closed; next work is one focused implementation task explicitly issued by user.

RECOMMENDATION | Approval record: user reviewed all five planning documents and approved D01-D09, D11-D20 and D23 as proposed; changed D10/D21/D22; added and approved D24. All records dated **2026-10-10** (Asia/Karachi). There are **21 APPROVED, 3 CHANGED, 0 OPEN** decisions. The frozen contract is binding for later tasks; architecture.md gives the full field schema.

RECOMMENDATION | REQUIREMENT denotes the PDF; RECOMMENDATION denotes approved engineering choices or researched observations, not extra PDF requirements. Historical specification ambiguities below are resolved by their recorded choices. UNVERIFIED marks external facts/measurements still needing evidence; approval does not mark an access, license, quota, size or performance gate passed. Source: `../Requirements/fs-assessment-spotter.pdf`, pages 1-2; official-document research date: 2026-10-10.

RECOMMENDATION | User constraints: RouteShield is the working name; free tier only, no required card or paid upgrade; stop and tell the user if payment/card is required. User creates the TomTom key and Cloudflare/Render accounts later; credentials stay in local .env files/host dashboards and are never requested in chat. Windows PowerShell local commands and Linux CI/hosting commands. The completed approval task changed documentation only. The subsequent foundation task explicitly authorizes project-local approved dependencies, Git initialization/local commits and safe examples; no remote, push, real secrets, provider calls or feature logic.

## Printed rules, without interpretation

REQUIREMENT | These are the PDF's exact numerical bands. Units are printed on the first band of each row. Endpoint conflicts are deliberately preserved here.

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind | <25 mph | 25-34 | 35-44 | 45-54 | >=55 mph |
| Rain | <0.10 in/hr | 0.10-0.25 | 0.25-0.50 | 0.50-1.00 | >1.00 |
| Snow | <0.5 in/hr | 0.5-1.0 | 1.0-2.0 | 2.0-3.0 | >3.0 |

REQUIREMENT | The three load rules are: wind >=55 mph -> No Travel for any load; wind 45-54 mph and load >30,000 lb -> No Travel; wind 35-44 mph and load >40,000 lb -> Severe.

REQUIREMENT | Route priorities are, in order: fewest Severe miles, fewest High miles, lowest average risk, shortest travel times. The PDF does not define combination, mile ownership, ordinal values, UNKNOWN, or No Travel route ordering.

## D01 - Continuous boundaries and strict load thresholds

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User approved continuous boundaries without rounding, higher severity at shared precipitation endpoints, and strict load comparisons.
- RECOMMENDATION | Resolved context: Wind fractions in (34,35), (44,45), and (54,55) are not covered by the printed integer endpoints. Rain overlaps at 0.25 and 0.50; snow overlaps at 1.0 and 2.0. General half-open notation must not override the PDF's strict >1.00 rain and >3.0 snow cutoffs.
- RECOMMENDATION | Options: round to integers first; move gap values immediately to a worse band; extend each band to the next lower boundary without rounding. Approved choice: the third, with higher severity at shared precipitation endpoints: wind Low <25, Moderate [25,35), High [35,45), Severe [45,55), No Travel >=55; rain Low <0.10, Moderate [0.10,0.25), High [0.25,0.50), Severe [0.50,1.00], No Travel >1.00; snow Low <0.5, Moderate [0.5,1.0), High [1.0,2.0), Severe [2.0,3.0], No Travel >3.0. Extend load wind windows to [35,45) and [45,55) consistently.
- REQUIREMENT | Load comparisons are strictly >30,000 and >40,000, not >=. Exactly 55 mph is No Travel for any load. These operators need no reinterpretation.
- RECOMMENDATION | Consequence: one named backend threshold table; no pre-classification rounding or epsilon shift. Test every printed endpoint and every approved transition. This convention is conservative at shared endpoints, but the treatment of wind fractions is an interpretation that was explicitly approved on 2026-10-10.

## D02 - Individual hazards, combined risk, and wind metric

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User approved the maximum-hazard rule, separate load-adjusted wind, sustained wind, and ordinal scale as proposed.
- RECOMMENDATION | Resolved context: The PDF does not specify combining simultaneous hazards or sustained wind versus gusts.
- RECOMMENDATION | Options: maximum hazard severity; sum severities; add compound penalties. Approved choice: maximum of independent wind/rain/snow classifications, load-adjusted wind computed separately, then maximum of hazard maximum and load-adjusted wind. Keep individual, hazard-level, load-adjusted, and final results plus triggered reasons.
- RECOMMENDATION | Use non-gust 10 m wind speed. Gusts are optional display data and never affect ranking. LOW=1, MODERATE=2, HIGH=3, SEVERE=4, NO_TRAVEL=5 is an approved ordinal scale, not a calibrated probability.
- RECOMMENDATION | Consequence: deterministic explanations without invented compound-hazard rules; missing required fields follow D08. Extra gust data is cut before core work if time runs short.

## D03 - Required weather metrics and unit semantics

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User explicitly approved rain + showers and snowfall depth, replacing the rain-only default; water equivalent must not substitute for snow depth.
- RECOMMENDATION | Resolved context: Rain-only versus all liquid rainfall and snow-depth versus water equivalent can change classification. The PDF specifies rainfall and snowfall rates but does not name API variables or temporal averaging.
- RECOMMENDATION | Primary evidence: Open-Meteo distinguishes `rain` (large-scale systems), `showers` (convective), and `snowfall` (snow depth), with preceding-hour accumulations and explicit unit options. It reports wind separately from gusts. See [hourly definitions and units](https://open-meteo.com/en/docs). Approved choice: liquid rainfall = `rain + showers`; infer from these distinct documented components that this avoids omitting convective rain. The user explicitly approved this inference on 2026-10-10; it replaces the AGENTS rain-only default. Never use total `precipitation` or snow water equivalent as a shortcut.
- RECOMMENDATION | Options: rain only (simple but undercounts showers); rain plus showers (chosen); a different provider's explicit rain intensity. For snowfall use depth, not water-equivalent intensity. For hourly accumulation, convert depth to inches then divide by the interval duration in hours; label as hourly average rate, not an instantaneous observation.
- RECOMMENDATION | Request mph/inch explicitly; validate returned unit metadata independently for each field. Defensive conversions: mph = km/h / 1.609344 or m/s * 2.2369362921; rain inches = mm / 25.4; snow inches = cm / 2.54. Inch/hour inputs need no length conversion. Reject unknown units, negatives, non-finite values, or absent required components as unavailable. Preserve source units/components for diagnostics.
- RECOMMENDATION | Consequence: a missing `showers` value is missing rainfall, not zero; adapters must validate field availability in the selected model. No hidden 7:1 conversion from precipitation is allowed.

## D04 - Checkpoint spacing, geometry, ETAs, and input time

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User approved the common adaptive/selectable interval, provider-based timing, chainage, and timezone policy as proposed.
- REQUIREMENT | Weather must be sampled at 10 / 25 / 50 mile checkpoints using estimated arrival time.
- RECOMMENDATION | Resolved context: The PDF does not assign the intervals to distances or require uniform speed, local timezone display, driver breaks, or traffic features.
- RECOMMENDATION | Options: one hardcoded interval; user choice; adaptive default plus user choice. Approved choice: 10/25/50 selection with a common adaptive default based on the longest accepted route: <=100 miles -> 10; <=500 -> 25; longer -> 50. Include origin and destination once, even if the last segment is shorter. If the approved point budget is exceeded, increase to the next offered interval with a visible warning; if 50 is insufficient, fail with a clear trip-too-large message. Do not invent a fourth interval or silently disregard user choice.
- RECOMMENDATION | Use WGS84 route geometry cumulative traveled distance, not straight origin/destination distance or vertex count. Normalize provider timing anchors onto the same chainage; interpolate provider cumulative times between anchors. Origin elapsed=0; destination elapsed=route duration. No unannounced total-duration * distance-fraction fallback if timing anchors are invalid.
- RECOMMENDATION | Use UTC instants internally; departure input defaults to the visibly named browser timezone (not silently the origin timezone). Send an ISO 8601 offset and IANA timezone for consistency validation. Reject nonexistent DST wall times; require an explicit earlier/later offset for ambiguous repeated times. Local checkpoint display uses its IANA timezone, with explicit UTC fallback if unavailable. Get coordinate timezone metadata from the weather response with epoch timestamps; format against IANA rules, not a single fixed UTC offset for the whole trip.
- RECOMMENDATION | Approved limitation: travel time is continuous provider-estimated driving time without rest/fuel stops. The assessment does not supply a breaks model; disclose this limitation. No live traffic product is built.
- RECOMMENDATION | Consequence: fair spacing across all routes and realistic segment timing. Reuse the same chainage for ownership and heatmap points. Distances in meters until display/threshold conversion; 1 mile = 1609.344 m exactly.

## D05 - Hourly forecast selection and horizon

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User explicitly approved enclosing-hour selection, including its hourly averaging and horizon limitations.
- RECOMMENDATION | Resolved context: Nearest hour, enclosing accumulation interval, or interpolation can produce different outcomes. Hourly averages cannot resolve within-hour peaks.
- RECOMMENDATION | Options: nearest row with a later-hour tie; enclosing row; interpolate weather before classification. Approved choice: the row whose accumulation interval `(t-1h,t]` contains ETA: at 12:20 use the 13:00 accumulation row; at exactly 13:00 use 13:00. Use that row's wind point-time value and report both ETA and forecast timestamp. This approximates wind within one hour and avoids pretending precipitation belongs to the following hour. Do not interpolate categories or hourly rain totals.
- RECOMMENDATION | Fetch from the hour at/before departure through the ceiling hour of `max(departure+48h, latest_checkpoint_eta)`; require real returned timestamps covering each lookup. Represent every slider h=0..48 at departure+h, even if departure has minutes. A row absent from returned coverage is OUT_OF_HORIZON or MISSING_HOUR, never nearest-endpoint extrapolation. Do not round an out-of-range ETA back into range.
- RECOMMENDATION | Use hourly data for predictable batching. Sub-hourly data adds regional/model differences and is not needed for the PDF; leave it out. Hourly averages and wind at the selected row are explicit uncertainty limitations.
- RECOMMENDATION | Consequence: horizon acceptance is based on actual response data, not a promise that requesting a maximum number of days guarantees every variable. Future departure whose full corridor window is unavailable gets a visible partial window and warnings; no false fully available 48h forecast.

## D06 - Mileage attribution and average risk

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User approved midpoint mile ownership and the unrounded mile-weighted ordinal mean as proposed.
- RECOMMENDATION | Resolved context: PDF mileage attribution and averaging are undefined; counting checkpoint totals biases comparisons when spacing differs.
- RECOMMENDATION | Options: each checkpoint owns the following segment; worst endpoint owns the segment; midpoint ownership. Approved choice: midpoint ownership. For sorted distances s[0]=0..s[n]=L, boundaries are 0, adjacent midpoints, L; checkpoint i owns its boundary interval. Category miles sum ownership at exactly that final risk; Severe does not include No Travel, and High does not include Severe.
- RECOMMENDATION | Average risk = sum(owned_miles * final ordinal) / L only when all required observations are complete. Keep precision for ranking; round only display. Separate all five category miles and unknown miles; total equals route length. Partial routes have `average_risk=null` and may show explicitly labeled known-only average as a diagnostic that never enters ranking.
- RECOMMENDATION | Consequence: endpoint ownership works with short/final segments, no double-counting, and long-route comparisons are distance weighted. Ownership is an approximation between samples, not a verified continuous hazard boundary.

## D07 - No Travel and ordered route comparison

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User explicitly approved known No Travel blocking, null recommendation when all blocked, and a separate least-blocked diagnostic.
- REQUIREMENT | Preserve Severe miles -> High miles -> average risk -> duration, in that order.
- RECOMMENDATION | Resolved context: No Travel routing and exact ties are unspecified. The word "balancing" does not authorize arbitrary weights that reverse the printed order.
- RECOMMENDATION | Options: ignore blocking and use the four values; block known No Travel; add a weighted penalty. Approved choice: known No Travel blocks the route before comparison. Among complete nonblocked routes compare `(severe_miles, high_miles, average_risk, duration_seconds, stable_route_id)` lexicographically. Among complete blocked routes compare `(no_travel_miles, severe_miles, high_miles, average_risk, duration_seconds, stable_route_id)`. Every nonblocked complete route precedes every blocked complete route. Never round the numerical keys first.
- RECOMMENDATION | All blocked -> `recommended_route_id=null`, separate `least_blocked_route_id`, and "No safe route at this departure time and load" with explicit assessed-data wording. All incomplete -> no recommended ID, distinct incomplete-data message. If only one complete nonblocked option exists, label it "Best fully assessed available route" and disclose missing alternatives/coverage. D08 governs mixed cases.
- RECOMMENDATION | Break exact ties by a deterministic ID from canonical geometry, stable under provider response reorder; not a random UUID or request array order. Explain the first actual differentiator against each competitor and include compared raw values; human prose may round but must not claim an exact tie when only display values tie.
- RECOMMENDATION | Consequence: best fully assessed unblocked option under the assessment policy; there is no maximum allowed detour or weighted speed preference because neither is in the PDF.

## D08 - Missing, malformed, stale, and partially known weather

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User explicitly approved showing incomplete routes while leaving them unranked and never recommended; missing data cannot count as safe.
- RECOMMENDATION | Resolved context: The PDF has no missing-data policy. Excluding unknown miles from average while still recommending the route can reward lack of evidence.
- RECOMMENDATION | Options: unknown=Low (reject); unknown=No Travel (invented hazard); unknown separate/ineligible (chosen). A checkpoint with any missing required hazard is UNKNOWN, retaining known hazard results and `known_risk_floor`. A known No Travel wind/rain/snow or load trigger still sets `known_blocked=true`, even when final complete classification is UNKNOWN. Do not let UNKNOWN erase a known block.
- RECOMMENDATION | Incomplete routes are displayed in an unranked group and cannot be recommended or enter full-route averages. Complete routes alone enter D07. Return unknown miles, coverage fraction, known hazardous evidence, reasons, and a nullable average. Never report incomplete routes as unblocked; use `travel_status=BLOCKED|ASSESSED|INCOMPLETE` (BLOCKED if evidence proves it).
- RECOMMENDATION | If complete routes are all blocked and other routes are incomplete, say "No fully assessed travelable route"; do not assert all options are blocked unless each has known block evidence. A least-blocked complete diagnostic remains explicitly not recommended. If every route has known blocking evidence, show all-blocked warning even with extra unknown miles, and do not compare incomplete averages as known values.
- RECOMMENDATION | Cache age >15 minutes is stale for this application. Existing results stay inspectable with a stale banner but require explicit re-analysis for a current recommendation. A stale payload is not silently replaced or presented as newly fetched. Errors never populate success caches.
- RECOMMENDATION | Consequence: explicit eligibility replacing the former warning-only default; one partially failed batch cannot make a route look safest. Missing weather never becomes a zero value or risk ordinal.

## D09 - Routing provider, distinctness, and fewer alternatives

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User approved TomTom primary, bounded real-provider waypoint requests, and ORS as the conditional fallback; switching after a failed TomTom live gate requires a new user decision.
- REQUIREMENT | Generate three routes using an API. HGV-specific restrictions and a distinctness metric are engineering additions, not printed PDF mandates.
- RECOMMENDATION | Compare TomTom Routing + Geocoding with openrouteservice Directions (`driving-hgv`) + Pelias geocoding. TomTom's documented v1 API supports truck mode and up to five additional routes, explicitly permitting fewer results. Its extended polyline representation supplies cumulative distance and travel time at vertices; guidance also supplies cumulative anchors. Approved choice: `maxAlternatives=2`, `alternativeType=anyRoute`, truck mode, full geometry, and `extendedRouteRepresentation=distance` plus `extendedRouteRepresentation=travelTime`, after a live generation/access gate. Prefer these aligned vertex values; validated guidance anchors are a timing fallback. [Route options and extended representation](https://docs.tomtom.com/routing-api/documentation/tomtom-maps/v1/calculate-route), [guidance timing](https://docs.tomtom.com/routing-api/documentation/tomtom-maps/v1/guidance-instructions).
- RECOMMENDATION | openrouteservice is the fallback: native alternative requests have a 100 km cap and up to three routes, so it is unsuitable as a general long-haul primary. Its official SDK describes HGV and step duration/geometry options. [Restrictions](https://openrouteservice.org/restrictions/), [official Python API reference](https://openrouteservice-py.readthedocs.io/en/latest/openrouteservice.html#module-openrouteservice.directions). Do not treat an ordinary 6,000 km driving limit as the alternative-route limit.
- RECOMMENDATION | Distinctness options: unequal geometry bytes (too weak); shared vertices (resolution-dependent); sampled shared distance (chosen). Resample both geometries every 0.5 mile with weighted half-endpoint/final weights. A sample matches the other polyline within 100 m; directional overlap = matched owned length / total length. Symmetric overlap=max(A covered by B, B covered by A). Reject candidate when overlap >0.90 against any accepted route; 0.90 is allowed. Sort candidate canonical IDs before filtering; keep up to three. These tolerances are approved approximations, not provider guarantees; parallel nearby roads may be conservatively rejected.
- RECOMMENDATION | If fewer than three remain, optionally make at most two extra real-provider calls through deterministic intermediate positions (one on each side of the main corridor); same endpoints, truck profile, no synthetic line. Validate and discard duplicate/no-route candidates; cap added duration at 1.5 times the fastest route for this fallback search only, not for ranking native routes. Intermediate points are route-shaping requests, not a multi-stop trip feature.
- RECOMMENDATION | One/two routes after bounded attempts -> show available alternatives, `PARTIAL_ROUTES` warning and count, continue analysis; zero -> NO_ROUTE error. Graceful handling is required reliability, but fewer than three is not full fulfillment for that request. Select a verified three-route corridor for the assessment demo.
- RECOMMENDATION | Resolved context: Load weight is cargo weight, not gross truck weight. Approved choice: omit gross/axle/dimension restrictions until real truck specifications exist; use generic truck mode and disclose that it does not certify clearance/weight compliance. Do not invent tare or pass load weight as vehicle weight.
- RECOMMENDATION | Consequence: bounded quota use with genuine provider-derived routes. Only one provider integration is initially funded; fallback deployment requires user direction after a failed TomTom live gate, not an automatic switch. If no free truck alternatives or usable cumulative timing exist, STOP and ask before substituting ORS or another provider.

## D10 - Corridor forecast, heatmap semantics, and selection

- RECOMMENDATION | Status: CHANGED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User retained the departure-relative categorical heatmap and allowed playback, an ETA-derived truck marker and a payload-gated hazard filter to improve driver usability without provider calls.
- REQUIREMENT | Map all routes/checkpoints/risk/ETAs/summaries and provide a trip-corridor weather heatmap with a 0-48 hour slider.
- RECOMMENDATION | Resolved context: Slider reference time, corridor width, density, and relationship to arrival-time route risk are unspecified.
- RECOMMENDATION | Options: departure-relative vs now-relative; arrival-time route colors vs recomputed snapshot colors. Approved choice: departure-relative h=0..48 (49 frames), with absolute selected time and visible timezone. Checkpoint route analysis remains at each ETA; the heatmap is simultaneous corridor weather at departure+h. Show both values in details; slider changes do not rerank routes or change trip inputs.
- RECOMMENDATION | Sample along all returned route centerlines (not a global grid); checkpoints are mandatory points. Start additional corridor samples at 10 miles and coarsen only display samples within the 300-unique-coordinate budget. Deduplicate shared points within 100 m; map each route/checkpoint to its pooled point. Blur visually extends around samples; do not imply measured weather for every off-road location or road between sparse points. Display the actual density/spacing.
- RECOMMENDATION | Backend preclassifies every point/hour with the same risk function and load. Return all frames in one analysis response. Upstream batches are fetched once per analysis; slider uses no HTTP. Frame availability and UNKNOWN styling are explicit; neither is transparent-as-safe.
- RECOMMENDATION | For MapLibre use five categorical heatmap layers, each filtered to one final risk and using that category's constant hue with density controlling opacity only. Draw Low to No Travel, plus UNKNOWN hatch/gray markers; exact labeled circles/queries remain available above heatmap. Never map blended density back to risk bands: many Low points cannot become red/Severe. Layer blending denotes spatial coverage, not probability or an additional risk score. [Native heatmap](https://maplibre.org/maplibre-gl-js/docs/examples/heatmap-layer/), [layer semantics](https://maplibre.org/maplibre-style-spec/layers/).
- RECOMMENDATION | Consequence: a real weather-driven corridor overlay with stable risk meanings. Native slider, requestAnimationFrame-coalesced updates, persistent sources/layers, one map lifetime; acceptance evidence measures zero requests and actual frame timing.

- RECOMMENDATION | Changed additions: user-initiated play/pause advances the cached slider one hourly frame at a time; never autoplay, stop at h48, pause on manual scrub/new analysis/unmount. Honor reduced motion (start paused, no interpolated motion); no provider or browser requests on playback.
- RECOMMENDATION | Backend precomputes a truck position for each route/frame from the existing checkpoint elapsed times and distance chainage, placed on real geometry (not a straight line between checkpoints). Clamp at origin/destination and label estimated progress, not GPS tracking. Frontend selects the returned marker for its selected route; it does not recalculate ETAs.
- RECOMMENDATION | Optional hazard filter selects combined final risk, load-adjusted wind, rain or snow codes already calculated by the backend. It does not rerank or alter arrival-time summaries. Include per-frame hazard codes only when the complete compressed response remains <=500 KB; otherwise omit codes and filter, expose capabilities.hazard_filter=false, retain the combined view. Measure size; do not guess.
- RECOMMENDATION | Reason/consequence: these additions reuse fetched data and remain within D10/D23 budgets. Playback and truck marker are refinements time-boxed in M8; hazard filter is conditional P2 reserve work.

## D11 - Free-provider access, quotas, attribution, and license gates

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User approved provider quota/license gates, with the stronger constraint of free tier only and no card-required plan.
- RECOMMENDATION | TomTom currently lists 20,000 free monthly Routing requests and 20,000 Geocoding requests, with no upfront card; exceeded free limits return 429. Default routing/geocoding limits are 5 QPS. Use Geocoding for address suggestions/lookup, not a higher-cost POI feature. [Current pricing](https://docs.tomtom.com/pricing), [platform FAQ](https://docs.tomtom.com/platform/documentation/status-and-support/faqs), [QPS](https://docs.tomtom.com/platform/documentation/api-best-practices/qps-limits), [geocode](https://docs.tomtom.com/geocoding-api/documentation/tomtom-maps/v1/geocode).
- UNVERIFIED | TomTom's current legal page rendered a shell without operative API clauses: [terms entry point](https://docs.tomtom.com/legal/terms-and-conditions). Cross-basemap display permissions, applicable attribution text, stored result permissions, v1 service longevity, account entitlements, and actual key access must be confirmed before reliance. Retain returned attribution; use no shared route/geocode cache until storage terms are confirmed. Pricing alone is not license approval.
- RECOMMENDATION | Open-Meteo Free is non-commercial, with 600 calls/minute, 5,000/hour, 10,000/day, and 300,000/month listed; no uptime guarantee. Data needs CC BY 4.0 credit and notice of modifications. Keep below the thresholds, rather than using the exact limits as targets. The pricing calculator accounts for variables, length, models, and locations, so a batch is not automatically one quota unit. [Pricing/accounting](https://open-meteo.com/en/pricing), [usage terms](https://open-meteo.com/en/terms), [data license](https://open-meteo.com/en/licence).
- UNVERIFIED | A personal hiring-assessment demonstration may qualify as non-commercial. This is not established by provider wording; confirm the intended deployment use against the terms. If ineligible, do not purchase a plan or quietly proceed on the free endpoint.
- UNVERIFIED | The public ORS plan page redirected to a client-rendered account page. An official staging page lists Directions 2,000/day and 40/minute, geocoding 1,000/day and 100/minute; treat these as provisional until the live account dashboard confirms them. [Official staging plans](https://staging.openrouteservice.org/plans/), [live plan entry](https://openrouteservice.org/plans/).
- RECOMMENDATION | Consequence: free-only and no required card are gates; stop and tell the user if a provider/host requires payment or a card. The user creates credentials/accounts later; never request plaintext keys in chat. No paid upgrades or automatic spending path. Public demo receives throttling and bounded per-analysis work.

## D12 - Weather provider comparison

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User approved Open-Meteo primary and the documented conditional alternatives; no automatic or paid fallback is authorized.
- RECOMMENDATION | Primary: Open-Meteo, with D03-D05 normalization, batched coordinates, no-key setup, and returned horizon validation. Fallback: Tomorrow.io free forecast after a separate metric/entitlement gate; it documents 120h hourly forecasts, 500 requests/day, 25/hour, and 3/second. A typical multi-point corridor can consume that hourly budget quickly. [Forecast endpoint](https://docs.tomorrow.io/reference/weather-forecast), [free limits](https://support.tomorrow.io/hc/en-us/articles/20273728362644-Free-API-Plan-Rate-Limits).
- RECOMMENDATION | Tomorrow documents distinct rain and snow intensity/accumulation fields and metric/imperial units. [Core fields](https://docs.tomorrow.io/reference/data-layers-core), [availability](https://docs.tomorrow.io/reference/weather-data-layers). Prefer verified hourly snow depth accumulation over a potentially water-equivalent snow-intensity shortcut; investigate before switching.
- UNVERIFIED | Tomorrow's exact free entitlement to snowfall-depth accumulation, multi-location batching, commercial-use/redistribution terms, attribution, and whether its snow metric matches the PDF's depth convention were not established. It is a constrained candidate fallback, not a proven drop-in equivalent for a 300-point trip. Do not claim otherwise.
- RECOMMENDATION | Alternative considered: NWS is free/open US forecast data with unpublished rate limits and point/grid discovery; raw precipitation aggregation intervals and snow-depth availability need more adaptation than funded. It is not the chosen global fallback. [NWS official API](https://www.weather.gov/documentation/services-web-api).
- RECOMMENDATION | Consequence: implement one weather adapter first. If primary access fails, switching provider requires a correctness and quota check, not automatic metric substitution.

## D13 - Map engine and basemap comparison

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User approved MapLibre GL JS/OpenFreeMap and the documented map fallback as proposed.
- RECOMMENDATION | Primary: MapLibre GL JS with OpenFreeMap Positron or Liberty style and native categorical heatmaps (D10). It earns its heavier lazy chunk through GPU layers and incremental source updates. OpenFreeMap states no public-instance request/view limits and no key/account requirement; use modest traffic and do not infer an SLA. Preserve attribution to OpenMapTiles and OpenStreetMap, optionally OpenFreeMap. [Public instance](https://openfreemap.org/), [integration](https://openfreemap.org/quick_start/), [official attribution](https://github.com/hyperknot/openfreemap/blob/main/README.md).
- RECOMMENDATION | Fallback: Leaflet with standard OSM raster tiles and five constant-hue Leaflet.heat layers. Simpler 2D renderer and lower map-code weight, but canvas updates/plugins and risk-density semantics need verification. [Leaflet renderer/API](https://leafletjs.com/reference.html), [official heat plugin](https://github.com/Leaflet/Leaflet.heat). OSM standard tiles require visible attribution, correct identification/referrer, ordinary HTTP caching, and no bulk/offline prefetch; capacity is donated with no SLA. [Tile policy](https://operations.osmfoundation.org/policies/tiles/).
- RECOMMENDATION | MapLibre license verified as BSD-3-Clause from its [license](https://github.com/maplibre/maplibre-gl-js/blob/main/LICENSE.txt). Neither engine provides routing or weather. The basemap should be muted so categories remain readable.
- RECOMMENDATION | Consequence: no private map credentials in the browser. If WebGL or basemap fails, keep route cards/checkpoint table usable and expose a map error; a table-only state is reliability fallback, not complete PDF map fulfillment.

## D14 - Frontend tooling, language, and state comparison

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User approved React, strict TypeScript, Vite, plain CSS, TanStack Query and local interaction state as proposed.
- RECOMMENDATION | Primary: React + strict TypeScript + Vite, plain CSS, and local reducer/state for selected route/checkpoint/slider. Vite has React/TS templates; run TypeScript checking separately from transpilation. [Vite guide](https://vite.dev/guide/), [TypeScript handling](https://vite.dev/guide/features.html), [React reducer](https://react.dev/reference/react/useReducer).
- RECOMMENDATION | Fallback: React + TypeScript in a Next.js static export. It can serve static HTML assets, but introduces browser/server boundaries and feature restrictions that add little to a single-map Django-backed app. [Next static export](https://nextjs.org/docs/app/guides/static-exports). JavaScript is technically permitted but strict TS is worth the small setup cost for nested nullable data; do not use Next server routes for backend domain logic.
- RECOMMENDATION | Data options: TanStack Query vs native fetch + AbortController. Approved choice: TanStack for geocoding request cancellation/cache and one user-triggered analysis mutation; keep the returned 49-frame payload in memory. Disable retries for analysis, polling, focus/reconnect refetches of analysis, and queries keyed by slider position; explicit refresh only. Defaults can refetch/retry, so override deliberately. [TanStack defaults](https://tanstack.com/query/latest/docs/framework/react/guides/important-defaults).
- RECOMMENDATION | Native fetch is the dependency-saving fallback, with explicit cancellation and lifecycle states. No Redux/global store/router/form library needed for one page.
- RECOMMENDATION | Consequence: server state and interaction state stay separate, the slider never starts a query, and heavy map code loads only when map use is needed.

## D15 - Backend structure and API comparison

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User approved Django/DRF, pure dataclasses, synchronous HTTPX and stateless orchestration as proposed.
- REQUIREMENT | Django must be used.
- RECOMMENDATION | Primary: supported Django release compatible with Python 3.12+, DRF serializers/views, dataclasses for domain values, one orchestrator, and synchronous HTTPX with bounded I/O concurrency if needed. DRF earns its dependency with nested validation and consistent REST errors. [DRF serializers](https://www.django-rest-framework.org/api-guide/serializers/).
- RECOMMENDATION | Fallback: plain Django views + JsonResponse and explicit validators. Fewer packages, but more hand-built schema/error/throttle logic in a validation-heavy API. [Django views](https://docs.djangoproject.com/en/5.2/topics/http/views/). Choose DRF without models/viewsets/admin/auth features; no Pydantic on top of DRF, Redis, Celery, or microservices.
- RECOMMENDATION | Domain is pure Python; adapters normalize provider responses and validate transport shapes; orchestration coordinates them; API validates/serializes; React formats and selects already calculated results. Production checks follow [Django's checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).
- RECOMMENDATION | Consequence: stateless service compatible with ephemeral free hosts and small deterministic tests; exact versions and locks are chosen at setup, not installed during planning.

## D16 - Testing tool comparison

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User approved pytest/pytest-django, Vitest/Testing Library, Playwright and offline fixtures with separately observed live checks.
- RECOMMENDATION | Python primary: pytest parameterization + pytest-django for API integration; fallback: standard unittest + Django TestCase, which avoids a runner dependency but makes large boundary tables less concise. [pytest](https://docs.pytest.org/en/stable/), [unittest](https://docs.python.org/3/library/unittest.html). Use direct domain calls and injected fixture providers; no live calls in unit/integration tests.
- RECOMMENDATION | Frontend primary: Vitest + Testing Library; fallback: Jest + Testing Library. Vitest reuses Vite configuration while Jest requires an explicit TS/DOM transform setup for this stack. [Vitest guide](https://vitest.dev/guide/index.html), [Jest setup](https://jestjs.io/docs/getting-started). Test observable selection/error/slider behavior, not a duplicated TS risk engine.
- RECOMMENDATION | Browser primary: Playwright; fallback: Cypress. Both have retrying assertions; Playwright is approved for one isolated Chromium journey, request counting, and screenshots without a separate map-mock assertion masquerading as rendering evidence. [Playwright assertions](https://playwright.dev/docs/test-assertions), [Cypress retry behavior](https://docs.cypress.io/app/core-concepts/retry-ability).
- RECOMMENDATION | Consequence: exhaustive domain tests, focused adapter/API/component coverage, one deterministic full journey, one separately marked live-provider smoke, and actual hosted/browser visual checks. Browser downloads are dev-only future work; no package is added now.

## D17 - Frontend hosting comparison

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User explicitly approved Cloudflare Pages; the user will create the account later. Free access without a required card must be verified.
- RECOMMENDATION | Primary Cloudflare Pages: static Vite output, free 500 builds/month and one concurrent build, no frontend server required. [Limits](https://developers.cloudflare.com/pages/platform/limits/). Fallback Vercel Hobby: simple static deployment but restricted to personal/non-commercial use; exceeding many limits requires waiting rather than upgrading. [Hobby terms/limits](https://vercel.com/docs/plans/hobby).
- UNVERIFIED | Free account eligibility for an assessment deployment still requires verification. Account verification and any identity/card requirements were not inspected. Prefer default provided domains and no paid feature.
- RECOMMENDATION | Consequence: frontend deploy has only a public API URL; no provider keys or Django secret. Confirm browser actually uses production URL, not localhost.

## D18 - Backend hosting comparison

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User explicitly approved Render Free without keepalive pings; the user will create the account later. A card-required fallback is disqualified.
- RECOMMENDATION | Primary Render Free Web Service: 750 instance hours per workspace/month, sleep after 15 minutes idle, roughly minute-scale wakeup, ephemeral filesystem. Included bandwidth/build minutes apply; if no payment method is present, exhausted allowance suspends rather than billing supplementary bandwidth. [Free-service limitations](https://render.com/docs/free). Verify current account spending controls and remaining allowance before deployment.
- RECOMMENDATION | Fallback Koyeb Free: one service, 512MB RAM, 0.1vCPU, 2GB SSD, Frankfurt or Washington, sleeps after one hour; it is described for hobby/testing, not production-grade availability. [Instance limits](https://www.koyeb.com/docs/reference/instances). Lower CPU is a concern for large geometry; benchmark rather than assume.
- UNVERIFIED | Koyeb account card/identity eligibility and full account overage controls were not confirmed; it is conditional. Railway/Fly trials are not treated as durable free hosting without verified eligibility. Neither recommended free host gives the demo a production availability guarantee.
- RECOMMENDATION | Consequence: use environment-driven settings, Gunicorn, WhiteNoise, small worker/thread counts, no persistent DB requirements. Local Windows uses Django runserver; Linux host uses Gunicorn. No uptime automation that defeats free-tier sleep.

## D19 - Dependency gate and size impact

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User approved the dependency justification/license/size gate.
- RECOMMENDATION | No dependency was added by the approval documentation task. The authorized foundation pins the approved groups; see [dependencies.md](dependencies.md) for actual installed versions, licenses, purposes, measured sizes and audit evidence. Map dependencies remain deferred. Further additions still require this gate.

| Label | Approved dependency group | What it earns/replaces | Size/license treatment |
|---|---|---|---|
| REQUIREMENT | React/React DOM; Django | Mandated application runtimes | Verify licenses of pinned versions; unavoidable runtime cost |
| RECOMMENDATION | TypeScript/Vite/plugin-react/ESLint | Typed contract, build/dev/lint; replaces custom tooling | Mostly development-only; final runtime size measured; exact license inventory pending |
| RECOMMENDATION | TanStack Query | Geocoding/analysis request lifecycle; replaces hand-built fetch caching | Approved runtime addition; replacement with the considered native-fetch fallback must be recorded; license/version pending |
| RECOMMENDATION | MapLibre GL JS | Map, GPU line/circle/heatmap layers; replaces extra heat plugin | BSD-3-Clause verified upstream; largest lazy runtime chunk; report actual build size |
| RECOMMENDATION | DRF/HTTPX/django-cors-headers | Boundary validation, transport, explicit cross-origin config | Server-only; replaces manual schema/HTTP/CORS; pinned licenses pending |
| RECOMMENDATION | Gunicorn/WhiteNoise | Linux process/static serving | Production server-only; replaces dev server/ad hoc file serving; pinned licenses pending |
| RECOMMENDATION | pytest/pytest-django/Ruff/mypy/django-stubs | Deterministic tests/lint/types | Dev-only; scope stubs to strict domain/adapters if Django typing costs exceed budget; licenses pending |
| RECOMMENDATION | Vitest/Testing Library/DOM environment/Playwright | UI and full-browser checks | Dev-only; browser binaries/storage count as setup cost, not JS bundle; licenses pending |

- RECOMMENDATION | Prefer HTTPX directly over provider SDKs; standard dataclasses over another model library; built-in ThreadPoolExecutor over an async stack; plain CSS/system fonts over component/icon packages. No map React wrapper is necessary when one MapLibre instance can be managed in one component.
- RECOMMENDATION | Consequence: dependencies are justified before installation; optional additions can be cut while required correctness remains funded.

## D20 - Validation and supported-input limits

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User approved the documented input, timezone, weight, body-size and departure-range guards as proposed.
- RECOMMENDATION | Resolved context: PDF supplies no input bounds. Options: accept arbitrary text/weight/dates; constrain to a demonstrable envelope. Approved choice: trimmed location labels 2-200 characters with a selected geocoded candidate; WGS84 latitude [-90,90], longitude [-180,180]; finite cargo weight 0-100,000 lb inclusive, preserving decimal comparisons; explicit ISO offset; no past departures (five-minute clock grace), and maximum now+7 days as a product guard. This is not a legal load rating or forecast availability promise.
- RECOMMENDATION | Validate IANA timezone/offset consistency, identical endpoints after selection, impossible provider road snaps, JSON body size <=16 KB, interval in {10,25,50}, and all non-finite/boolean numeric inputs. More than one plausible geocoding result requires user selection, never blind first-match choice. Direct coordinate requests are allowed for deterministic testing; backend applies identical checks.
- RECOMMENDATION | Consequence: out-of-envelope API input fails before quota use; missing forecast coverage within the guard is still UNKNOWN with warnings, not fabricated. The user approved these time/weight limits on 2026-10-10, recognizing that they constrain usable trips.

## D21 - Batching, caching, timeouts, retries, and quota control

- RECOMMENDATION | Status: CHANGED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User raised the analysis allowance so reviewers can try several trips, and required a measured 300-coordinate quota cost before orchestration.
- RECOMMENDATION | Options: per-point calls; one unbounded URL; bounded pooled batches (chosen). Cap distinct pooled coordinates at 300, each batch at 50 and two concurrent batches. Include all risk checkpoints before additional display points. Reserve pessimistically at least one weather quota unit per coordinate until measured accounting is available; HTTP batch count is not quota cost. In the FIRST feasibility spike measure one uncached 300-coordinate analysis, including its actual variables, hourly window, models and all batches. Record evidence and quota units. If cost >100 units, propose a lower coordinate cap and obtain user direction BEFORE API orchestration; do not silently change 300 or claim a guessed measurement. These are application bounds, not an assertion of provider hard limits.
- RECOMMENDATION | Approved connect timeout 3s, routing read 12s, weather/geocoding read 8s; whole warm analysis deadline 35s. At most one retry for transient connection/502/503/504 failures with capped 0.5s backoff; respect Retry-After only within remaining deadline. No retry for invalid input/no-route/authentication; 429 gets a quota warning or controlled partial weather result. Fallback route calls count toward the same deadline.
- RECOMMENDATION | Cache successful normalized weather series for <=15 minutes keyed by provider/model, exact pooled coordinates, requested time window, variables/units; classifications also include load and policy version if cached. Coordinate dedupe tolerance is explicit, not a silent arbitrary rounding key. Never cache failure as zero/empty success. No shared provider route/geocode caching until D11's terms permit it; session memory only when permitted.
- RECOMMENDATION | Client: geocoding after >=3 characters with 400 ms debounce and abort previous call. Analysis mutation only on submit, no automatic retry. In-process per-IP throttle is 10 analyses/10min and 30 geocode queries/min/IP plus per-request budgets; account-aware global quota guard. DRF cautions its throttles are not a security/DoS protection guarantee. [Throttle limitations](https://www.django-rest-framework.org/api-guide/throttling/).
- RECOMMENDATION | Consequence: predictable bounded work, fast failure, partial weather within 35s where possible; totals and warnings expose coarser sampling or unavailable batches. No queue/job/result database.

## D22 - UX and accessibility

- RECOMMENDATION | Status: CHANGED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User funded restrained theme, typography, motion and a risk-profile strip because UI/map/heatmap is 35% of the assessment; these refinements are P2 and cut first at missed time gates.
- RECOMMENDATION | One calm dispatch-planning page: white/off-white cards, dark navy text, system sans typography, 8px spacing rhythm, compact form, clear comparison rail, large muted map. Recommendation and first deciding metric appear before detailed weather. Desktop split rail/map; narrow screens show form, recommendation, cards, map, slider without horizontal page scrolling.
- RECOMMENDATION | Risk semantics: green Low, amber Moderate, orange High, red Severe, dark plum No Travel, neutral gray UNKNOWN, always with text/icon/pattern. Route identity is encoded by labeled line style/outline, while hazard segments use risk color. No separate route palette that changes the meaning of red.
- RECOMMENDATION | Native inputs/buttons/slider, explicit labels and lb/miles/UTC-zone indicators, visible focus, keyboard route/checkpoint list equivalent to map clicks, non-color legend, >=4.5:1 ordinary text contrast, reduced-motion preference, restrained transitions, and accessible live status/errors. Avoid repeated announcements for every scrubbed frame.
- RECOMMENDATION | Consequence: empty/loading/wakeup/error/partial/unknown/blocked/stale states are designed, not bolted on. Advisory copy: "Weather-based planning aid. Forecasts and truck restrictions may be incomplete; verify conditions and road restrictions before travel."

- RECOMMENDATION | Changed visual direction: light/dark theme via CSS custom properties/plain CSS, initial system preference plus manual toggle; refined system font scale. A single self-hosted variable font is optional only after verifying license and keeping D23 JS/payload budgets plus reporting actual font bytes. No UI kit.
- RECOMMENDATION | Purposeful motion: route draw-in, staggered result entrance, one-time metric count-up, eased camera moves, skeleton loaders and selection transitions. DOM effects use CSS/Web Animations on transform/opacity only; reserve metric widths and update count text without layout shifts. Use existing map camera controls for bounded easing, with instant changes under reduced motion. No motion library unless justified through D19.
- RECOMMENDATION | A small risk-profile strip/SVG plots the selected route's distance using backend midpoint-owned risk segments; no frontend classification or chart library.
- RECOMMENDATION | Budget priority: theme, font, motion and profile are P2, funded only inside M7-M9/reserve. If any 7h/10.5h/13.75h gate is missed, cut remaining P2 work in plan.md's exact order; accessible base styling, loading status and reduced-motion support remain mandatory.

## D23 - Production, security, performance evidence, and scope

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: User approved production safeguards and measured performance budgets as proposed; targets are not measurements.
- RECOMMENDATION | Explicit DEBUG=False, ALLOWED_HOSTS, CORS allowlist, server secrets, HTTPS/proxy settings, secure cookies if used, health liveness independent of providers, no admin/auth endpoints needed. Redact credentials/query strings and unnecessary locations from logs; external URLs are fixed adapter endpoints to prevent arbitrary URL fetching. No secret in Vite env or client payload.
- RECOMMENDATION | Performance targets (engineering budgets, not PDF numbers): 300 points /49 frames; <=500 KB compressed typical analysis response; initial JS <=200 KB gzip excluding lazy map; scrub frame p95 <=16.7 ms on documented desktop hardware, no sustained long tasks >50 ms, zero requests at fixed viewport, no unrelated form/route-card rerenders. These numbers are targets; actual results remain UNVERIFIED.
- RECOMMENDATION | Measure actual build output, network counts, frame intervals, interaction latency, and cold/warm end-to-end time; do not equate requestAnimationFrame alone with proving 60 fps. Report device/browser/data size and any missed target. Exact risk values come from the backend; incremental map updates never recreate the map on each slider/selection change.
- RECOMMENDATION | Consequence: scoped production demonstration and observable reliability, not a guaranteed safety system. Optional CI and OpenAPI generation fit only within the fixed allocations in `plan.md`.

## D24 - Deterministic, clearly labeled simulation weather

- RECOMMENDATION | Status: APPROVED; approval date: **2026-10-10**.
- RECOMMENDATION | User reasoning: calm real forecasts could hide the risk logic. Labeled deterministic scenarios let reviewers and the Loom show risk levels and recommendation branches while exercising the real implementation.
- RECOMMENDATION | Context/options: live-only demos are uncontrollable; overriding final scores would bypass correctness. Choice: a scenario weather provider behind the same forecast_series(points,window) interface, using deterministic location/time fields and the same normalized weather shape.
- RECOMMENDATION | Presets and stable IDs: All clear (all_clear), High-wind corridor (high_wind_corridor), Winter storm (winter_storm), Heavy rain front (heavy_rain_front), Blocked trip (blocked_trip), Tie-break (tie_break). Weather generation is independent of load; load effects come only from the real risk rules.
- RECOMMENDATION | Live is the default. Absent/null simulation_scenario means live; an explicit valid preset selects simulation only if server SIMULATION_ENABLED permits it. No silent switch or mixing, including partial failures, cache hits and stale results. Reject disabled/unknown presets before provider work. Routing remains real in the app; test routing/geocode fixtures are separately labeled.
- RECOMMENDATION | Every simulated analysis success/error carries is_simulation=true and simulation_scenario; live results carry false/null. UI preserves a persistent SIMULATION banner and scenario-name badge on all simulated results/error/stale states. Mode changes require explicit re-analysis; old snapshots retain their own labels until replaced atomically.
- RECOMMENDATION | Cache/source identity includes live/scenario provider, preset and version. Simulated observations never populate live weather caches. No live weather call in simulation; normal routing quotas still apply. Same risk/aggregation/recommendation pipeline, with no preset-specific scores or ordering shortcuts.
- RECOMMENDATION | Intended evidence: All clear -> Low/fastest; high-wind bands 35/45 mph -> strict load escalations and blocked eligibility; Winter storm -> Moderate/High/Severe snow and Severe-mile comparison; Heavy rain front -> rain-driven High/Severe and High-mile comparison, plus an equal-Severe/High fixture for average-risk comparison; Blocked trip -> wind55 at every point, all blocked/null recommendation; Tie-break -> equal risk metrics, duration then stable ID. Different geometry/timing fixtures exercise the actual comparison; do not promise the same winner on arbitrary live routes. Existing UNKNOWN fixtures cover unavailable-data branches without inventing a seventh preset.
- RECOMMENDATION | Consequence: six reproducible weather presets, default-off/config-disableable selector, source labeling and deterministic browser evidence. Fund implementation/verification inside M9 with ordinary fixtures; no new service, dependency, endpoint or ranking rule.

## Approval record and remaining evidence gates

RECOMMENDATION | All 24 decisions have explicit status, user reasoning and approval date above; no decision is OPEN. Replacing any approved policy requires a recorded user decision. Considered alternatives remain documented for comparison; they do not authorize a silent primary-provider switch or bypass free/no-card/license constraints.

UNVERIFIED | Remaining gates: actual TomTom entitlement/generation/terms/attribution, live truck alternatives and cumulative timing; Open-Meteo free-use eligibility, required variables/horizon and measured quota cost for 300 coordinates; fallback weather snow-depth/batching rights, ORS live dashboard quotas; host no-card eligibility/allowances; exact dependency versions/licenses/sizes and measured performance. These are future evidence gates, not unresolved choices or claimed passes. A failed TomTom gate requires STOP/user direction; >100 measured weather units requires a lower-cap proposal before orchestration; any payment/card requirement requires STOP/user direction.
