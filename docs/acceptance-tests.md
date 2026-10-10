# RouteShield acceptance and boundary tests

RECOMMENDATION | Status: APPROVED SPECIFICATION, 2026-10-10. These are specifications, not tests already implemented or executed. Numerical interpretations follow [decisions.md](decisions.md). Use fixed fixtures, injected provider clients, and a frozen clock; ordinary tests prohibit outbound routing/weather/geocode calls. Planned file paths are in [requirements-traceability.md](requirements-traceability.md).

REQUIREMENT | The target assessment journey is enter origin/destination/departure/load -> three API routes -> ETA-sampled risk -> ordered recommendation -> inspect map/checkpoints/summary -> scrub corridor forecast +0..48 h. React and Django, a hosted app, GitHub repository and 5-10 minute Loom are required.

## RISK: exact rules and approved boundaries

RECOMMENDATION | RISK-01..03 are parameterized pure tests. At each listed boundary b, test b-epsilon, b, b+epsilon with epsilon=0.0001 in that hazard's normalized unit; do not round. The table's labels mean expected severity under APPROVED D01, not printed PDF endpoint resolution. Other hazards=0, load=0 unless stated.

| ID | Hazard boundary | Just below | Exactly | Just above |
|---|---:|---|---|---|
| RISK-01 | Wind 25 mph | Low | Moderate | Moderate |
| RISK-01 | Wind 34 mph | Moderate | Moderate | Moderate |
| RISK-01 | Wind 35 mph | Moderate | High | High |
| RISK-01 | Wind 44 mph | High | High | High |
| RISK-01 | Wind 45 mph | High | Severe | Severe |
| RISK-01 | Wind 54 mph | Severe | Severe | Severe |
| RISK-01 | Wind 55 mph | Severe | No Travel | No Travel |
| RISK-02 | Rain 0.10 in/hr | Low | Moderate | Moderate |
| RISK-02 | Rain 0.25 in/hr | Moderate | High | High |
| RISK-02 | Rain 0.50 in/hr | High | Severe | Severe |
| RISK-02 | Rain 1.00 in/hr | Severe | Severe | No Travel |
| RISK-03 | Snow 0.5 in/hr | Low | Moderate | Moderate |
| RISK-03 | Snow 1.0 in/hr | Moderate | High | High |
| RISK-03 | Snow 2.0 in/hr | High | Severe | Severe |
| RISK-03 | Snow 3.0 in/hr | Severe | Severe | No Travel |

RECOMMENDATION | Additionally test zero, positive within-band values, wind fractions 34.5/44.5/54.5, and negative/non-finite inputs. Negatives, NaN, infinity, booleans, missing/null values do not enter numeric classification as Low.

| ID | Given/action | Expected |
|---|---|---|
| RISK-04 | Cartesian parameterization of wind {34.9999,35,44,44.5,44.9999,45,54,54.5,54.9999,55,55.0001} and load {0,29999.9999,30000,30000.0001,39999.9999,40000,40000.0001} | All three load rules apply with strict operators; [35,45) escalates only >40000; [45,55) blocks only >30000; >=55 blocks every tested load |
| RISK-04 | 45 mph, exactly 30000 lb; 35 mph, exactly 40000 lb | Load-adjusted wind Severe and High respectively; no equality escalation |
| RISK-04 | 44.9999 mph /40000.0001 lb; 45 mph /30000.0001 lb | Severe and No Travel respectively; no preclassification rounding |
| RISK-05 | Wind 10, rain .30, snow 2.5, load 0 | Individual Low/High/Severe; hazard max Severe; load-wind Low; final Severe with snow reason |
| RISK-05 | Wind 35, rain 0, snow 0, load 40000.0001 | Hazard High; adjusted wind Severe; final Severe with load reason |
| RISK-05 | Wind 35, rain 1.0001, snow 0, load 40000.0001 | Hazard No Travel, adjusted wind Severe, final No Travel; explain rain and load separately |
| RISK-05 | All hazards zero vs each individual hazard at its No Travel threshold | All-zero Low; rain/snow strict > maxima, wind >=55; final max regardless of other hazards |
| RISK-06 | Wind 10, gust 60, rain/snow zero; then wind 55, gust missing | First is Low (gust display cannot escalate); second No Travel; missing optional gust does not make required data incomplete |
| RISK-07 | Rain missing, other known Low | Final UNKNOWN, no ordinal, known floor Low, unavailable reason; never Low overall |
| RISK-07 | Wind 55, rain missing | Final UNKNOWN plus known floor No Travel and known_blocked=true; unknown cannot erase block |
| RISK-07 | Required rain/showers/snow/wind components each null/missing/malformed separately | Appropriate unknown field/reason, no zero fallback; all four result layers retain available evidence |

## CP and MET: geometry, ETA, mileage, metrics

| ID | Given/action | Expected |
|---|---|---|
| CP-01 | Synthetic multi-segment 23-mile path, interval 10 | Checkpoints at 0,10,20,23 along traveled geometry; exact destination once; no straight-line shortcut |
| CP-02 | Path lengths 5,10,20,23 with interval 10 | Respectively [0,5], [0,10], [0,10,20], [0,10,20,23]; endpoints neither omitted nor duplicated |
| CP-03 | Default against longest-route lengths 100,100.0001,500,500.0001 mi; user chooses each offered interval | Defaults 10,25,25,50; explicit choice retained unless documented cap intervention; same effective interval for all routes |
| CP-04 | Timing anchors distance 0/10/20 mi and elapsed 0/600/1800 s; checkpoint at 15 mi | Elapsed 1200 s, not 1350 s from total uniform-speed fraction; destination arrival departure+1800 s |
| CP-05 | Unequal geometry/provider distances, duplicate geometry vertices, zero-length step, monotonic loop path | Provider-calibrated chainage maps to real path; summary endpoints preserved; no divide-by-zero/shortcut; invalid/decreasing/unmappable timing returns a typed failure |
| CP-06 | UTC departure crossing local midnight, US timezone boundary and DST transition | Absolute elapsed unchanged; correctly dated/localized ETA with IANA timezone; missing zone explicitly UTC, not browser zone disguised as checkpoint local time |
| MET-01 | Checkpoints [0,10,20,23] | Owned miles [5,10,6.5,1.5], sum 23; disjoint category partition |
| MET-01 | Short 5 mi route [0,5]; exact 20 mi [0,10,20] | Owned [2.5,2.5] and [5,10,5] |
| MET-02 | [Low,Severe,High,Low] for 23 mi case | Low=6.5, Severe=10, High=6.5; Moderate/No Travel/Unknown=0; average=66/23, unrounded |
| MET-03 | Replace 20 mi checkpoint with UNKNOWN | Unknown=6.5 mi, coverage=16.5/23; full average=null; known-only diagnostic if present=46.5/16.5, never used for ranking |
| MET-03 | UNKNOWN includes known No Travel floor | Ownership remains UNKNOWN partition; separate known-block evidence does not double-count total length |
| MET-04 | Mixed five categories, intervals 10/25/50, shorter final segment | Sum categories+unknown equals full length; category miles use exact level; No Travel not counted again in Severe; aggregation unaffected by display rounding |

## RANK: priorities, exclusions, explanation

RECOMMENDATION | Construct complete route-summary fixtures directly for ordering tests; these test comparison, not repeated sampling setup. Ordinal averages must be valid for their fixtures; no randomly generated request order.

| ID | Given/action | Expected |
|---|---|---|
| RANK-01 | A vs B each differ in first criterion: A has fewer Severe miles but more High, higher average and longer time | A wins; later values cannot outweigh Severe |
| RANK-02 | Equal Severe, A fewer High but higher average/longer | A wins on High |
| RANK-03 | Equal Severe/High, A lower average but longer | A wins on average |
| RANK-04 | Equal Severe/High/average, A shorter duration | A wins on duration; exact all-four tie breaks canonical ID |
| RANK-04 | Provider returns equal-score routes in all six permutations | Stable route IDs, chosen route and explanation unchanged |
| RANK-05 | A complete unblocked Severe route vs B with one known No Travel checkpoint | A eligible before B, even if B has zero Severe miles; block cannot exploit exact-category counting |
| RANK-06 | All three complete routes blocked, No Travel miles 20/10/15 | No recommended ID; diagnostic second route; prominent no-safe-route warning; ties continue Severe/High/average/time/ID |
| RANK-07 | A incomplete with apparently low known average vs B complete nonblocked | A unranked/ineligible; B best fully assessed route with coverage warning; no UNKNOWN=Low |
| RANK-07 | All incomplete; then complete blocked routes plus one incomplete without known block | No recommendation; incomplete-data message in first case; "No fully assessed travelable route" in second; no false "all blocked" assertion |
| RANK-07 | All routes contain known No Travel evidence, some also unknown | No recommendation and all-blocked warning; incomplete averages never used to invent diagnostic order |
| RANK-08 | Winning differentiator changes between Severe, High, average, time, exact tie; display numbers round alike | Explanation generated from actual comparison facts for each competitor; precise differentiator despite display rounding; no hardcoded safe/fast claim |

## ROUTE: provider integration and distinctness

| ID | Given/action | Expected |
|---|---|---|
| ROUTE-01 | Recorded valid truck response with primary +2 alternatives | Three normalized provider fixture routes, profile/geometry/timing/summary/attribution preserved; request includes truck/alternatives and extended distance/time values; no cargo passed as gross weight |
| ROUTE-02 | TomTom lat/lon plus vertex cumulative distance/time; valid guidance fallback; ORS GeoJSON/steps in separate adapter fixtures | Canonical [lon,lat], meters, seconds; vertex timing alignment and monotonic guidance mapping; missing both fails safely; no swapped hemisphere |
| ROUTE-03 | Same path with different vertex densities or directionally asymmetric overlap | Length-weighted comparison stable; reversed/contained near-clone rejected using max directional coverage; distinct roads outside tolerance accepted |
| ROUTE-03 | Overlap exactly .90 and just above .90; 100m tolerance edge; unequal final samples | .90 allowed, >.90 rejected; tolerance inclusive; weighted sample ownership handles final length |
| ROUTE-04 | Provider returns 1/2 routes; allowed fallback returns new real routes or duplicate/no-route | <=2 extra calls, same endpoints/profile, bounded deadline/detour search; never clone offset geometry; return truthful count/warning if still <3 |
| ROUTE-05 | Provider returns no routes; ORS alternatives on >100 km request | NO_ROUTE or clear limit error; no fabricated options and no silent reuse of primary route |
| ROUTE-06 | 429, transient timeout, 503, malformed geometry/summary/timing, missing keys, invalid coordinates | Typed failure, bounded retries per D21, safe API mapping; no unbounded loop, no success cache for failure |
| ROUTE-07 | Explicit optional live smoke in the later authorized spike, both short/long demo corridors | Actually obtain three distinct truck routes on at least one repeatable corridor and valid arrival timing; log observed count/profile/latency; skipped unless credentials/authorization exist |

## WX: forecast adapter, units, time, missing data

| ID | Given/action | Expected |
|---|---|---|
| WX-01 | Inspect outgoing forecast request fixture | Required wind/rain/showers/snowfall; mph/inch explicit; UTC epochs and timezone metadata; batched coordinates; not precipitation used as rain |
| WX-02 | wind=16.09344 km/h; rain=6.35 mm over 1 h; snow=2.54 cm over 1 h; equivalent inch/mph fixture | Normalize 10 mph / .25 in/hr /1 in/hr; identical classification; snowfall depth is not water equivalent; validate metadata even with requested inch units |
| WX-02 | Hourly rain=.20, showers=.10 inches; no snow | .30 in/hr High, preserve components; missing showers -> UNKNOWN, not .20 |
| WX-03 | 13:00 row owns accumulation (12:00,13:00]; ETA 12:00,12:00:01,12:20,12:30,13:00,13:00:01 | Respectively 12:00,13:00,13:00,13:00,13:00,14:00 rows; expose wind forecast timestamp separately; no nearest-row substitution |
| WX-04 | ETA equals first/last available timestamp; one second outside; missing interior hour | Exact endpoints available if required fields valid; outside never rounded into horizon; missing-hour distinguished from out-of-horizon; no extrapolation |
| WX-05 | Departure minutes nonzero; departure+48 h exceeds provider last row; destination ETA >48 h | Exactly 49 frame times departure+h; unavailable tail explicit; fetch window covers latest ETA as well as slider; late checkpoint never omitted |
| WX-06 | Null/absent arrays, mismatched lengths, unsorted/duplicate timestamps, unknown units, negative/nonfinite values, swapped batch count | Validate alignment; bad points/hours become unknown or typed batch error; never associate location A's weather with B silently |
| WX-07 | 125 pooled points; repeated/shared positions; one of three <=50-coordinate batches fails | Dedup mapping stable; bounded batches/concurrency; failed points explicitly unavailable, good points retained; no per-checkpoint fetch loop |
| WX-08 | Same coordinates/window with changed units/model, later expiry, changed load | Correct complete cache key; no stale hit past 15 min; load-specific frames recomputed; normalized weather may safely reuse; failure never cached as success |
| WX-09 | Provider429/timeout/503 with and without Retry-After; deadline nearly exhausted | <=1 permitted transient retry; respect remaining deadline; unknown partial or mapped error; no auto-repeat that exceeds quota |
| WX-10 | UTC epoch series across DST and a real separately marked live sample in the later authorized spike | DST displays with IANA rules; live check confirms fields/units/horizon actually returned; unit suite remains offline and deterministic |
| WX-11 | First feasibility spike measures one uncached live 300-coordinate analysis, actual variables/hourly window/models and all <=50-coordinate batches | Record quota units with provider accounting evidence and request parameters, not HTTP count or estimated cost; >100 units requires a lower-cap proposal/user direction before API orchestration; exactly100 does not trigger this rule. If measurement cannot be established, gate remains UNVERIFIED and orchestration waits; simulation is not quota evidence |

## API: real HTTP validation and orchestration

| ID | Given/action | Expected |
|---|---|---|
| API-01 | Health request and valid route analysis to real Django test server with injected fixtures | Health 200 without upstream calls; analysis 200 with routes, recommendation/facts, warnings, exactly 49 frames and matching point arrays |
| API-02 | Empty/overlength label, missing candidate, same endpoints, out-of-range coordinates, huge body, invalid interval | Consistent400 field errors before any provider call; editable UI values preserved |
| API-03 | Load -1,0,30000,40000,100000,100000.0001,NaN,boolean; naive/invalid ISO dates; past/>7 days departures | Finite bounds enforced; valid exact thresholds accepted unchanged; required timezone-aware offset; frozen clock removes flaky dates |
| API-04 | NY 2026-03-08 02:30 nonexistent; NY 2026-11-01 01:30 repeated -04/-05; mismatched IANA offset | Gap rejected; repeated time requires explicit offset and maps to distinct UTC instants; invalid zone/offset rejected; freeze clock appropriately for these fixtures |
| API-05 | Valid routes + partial weather, all weather failed, 1/2 routes, all blocked | Honest200 partial/unknown/blocked status, null recommendation where needed; no unsafe zero values or dummy route |
| API-06 | Inject no-route/429/timeout/malformed upstream/unexpected exception | Correct documented404/429/504/502/500 and uniform `error` fields; no stack traces, URLs with keys or secrets |
| API-07 | Autocomplete ambiguity/no results, 400 ms debounce fixture, older analysis resolves after newer one | Candidate choice required; empty list shown; stale geocode/analysis cannot overwrite current selected input/results |
| API-08 | Exceed local request/body/coordinate budgets and remaining provider quota | Predictable limit error with safe retry hints; few provider calls; throttle acknowledged as best effort, not abuse-proof; no error cache |
| API-09 | Frozen-clock per-IP windows: analyses1..10 in10min, then11th; geocode1..30 in1min, then31st; second IP and global quota exhaustion | First10/30 allowed subject to global budgets; next gets429/retry hint before provider work; window expiry allows again; second IP still respects shared quota; local throttle is best effort, not DoS-proof |

## UI, MAP, HEAT: interactive and visual behavior

| ID | Given/action | Expected evidence |
|---|---|---|
| UI-01 | Empty app, valid geocoding, edited selected text, invalid form | All fields/units/timezone labeled; guidance useful; edited selection invalidated; keyboard submit/field errors work |
| UI-02 | Three complete routes with known winner | Winner/reason obvious before detailed map exploration; miles/duration displayed consistently; route cards select map and reverse selection works |
| UI-03 | Loading, cold health, timeout, provider error | Accessible actual status, bounded 90 s wakeup, cancellation/retry, preserved input; no fabricated stage progress or endless spinner |
| UI-04 | Fewer alternatives, all blocked, all unknown, partly missing horizon, stale result | Count/coverage/time/reason warnings; no false recommendation; unknown visible and never styled Low; timestamps disclose age |
| UI-05 | Keyboard-only, 375 px mobile and 1440 px desktop, reduced motion | Meaningful labels/focus, route/checkpoint list equivalence, accessible legend, readable contrast; no page overflow or hidden mandatory actions; screenshots inspected |
| UI-06 | Light/dark system preference, manual toggle, both themes at mobile/desktop | CSS variables/plain CSS; manual override honored, system choice used initially; risk meanings/labels/contrast/focus unchanged; no UI kit; optional font license and actual bytes reported within D23 budgets. P2 skip/cut is explicit |
| UI-07 | Route reveal, staggered result entrance, one-time count-up, bounded camera easing, skeletons, selection; repeat with reduced motion | CSS/Web Animations DOM effects change only transform/opacity, metric widths reserved, no motion-induced layout shift; existing renderer camera controls only; reduced motion immediate/static; no animation library without D19 justification; cleanup on replacement/unmount. P2 skip/cut is explicit |
| UI-08 | Selected route distance-risk profile at irregular endpoint spacing and UNKNOWN | Small SVG/strip uses backend start/end mile ownership and risk codes; matches MET-01 partition, no frontend thresholds or chart dependency; text equivalent/labels, updates route selection without HTTP. P2 skip/cut is explicit |
| MAP-01 | Real map with three fixture route geometries | All routes, risk segments, checkpoints, map-linked summaries, ETA/weather detail and legend actually render; screenshot, not merely source existence |
| MAP-02 | Card -> route click -> marker click -> different route | One synchronized route/checkpoint selection; selected outline visible, other routes remain; incompatible checkpoint reset |
| MAP-03 | Low through No Travel and UNKNOWN | Same labels/colors across legend/cards/segments/markers; route identity labels/styles separate from severity; no color-only meaning |
| MAP-04 | Map load/style/network/WebGL failure, resize, unmount/remount | Text results remain usable with map error; proper resize/cleanup; no duplicate listeners/maps or leaked animation frames |
| MAP-05 | Basemap and data credit at desktop/mobile sizes | Required map-corner attribution remains visible; weather/provider credit present; advisory visible |
| HEAT-01 | Three routes' pooled points at h0,24,48 | All routes contribute, real fixture weather changes risk/overlay; exactly 49 locally supplied frames; no decorative static red ribbon |
| HEAT-02 | Submit once, settle assets, fix viewport, scrub0..48 repeatedly | Zero initiated HTTP requests during scrub, including analysis/weather/geocode; use browser request-event instrumentation (not only network transfer cache hits); sliders create no query |
| HEAT-03 | 12:20 departure + slider h1 vs checkpoint ETA14:10 | Snapshot label13:20 absolute; arrival data remains14:10 with separate row timestamp; no reranking or changed ETA badges |
| HEAT-04 | Many duplicated/nearby Low points then one Severe point | Low hue remains Low regardless of density; Severe category remains recognizable; density never feeds a numeric classification; pooled duplicates do not multiply risk |
| HEAT-05 | Unknown/out-of-horizon frame points, including a known No Travel floor | Explicit gray/pattern points and frame coverage warning; proven block evidence stays visible; missing is neither silently transparent nor Low |
| HEAT-06 | 300 points, long routes, repeated slider movement, route changes | Bounded point density displayed; single map lifetime and incremental source updates; no dropped mandatory checkpoint to meet heatmap budget |
| HEAT-07 | Native slider keyboard arrows/Home/End and screen-reader labels | Correct h/time labels and focus; no flood of live announcements; respects reduced motion |
| HEAT-08 | Fresh result, explicit Play/Pause, manual scrub, new analysis/unmount, h48, reduced motion | Starts paused, never autoplay; discrete cached hourly frames, stop at48, pause/cleanup correctly; zero initiated HTTP requests, no reranking; reduced-motion transitions absent, accessible labels/status |
| HEAT-09 | Unequal checkpoint ETAs, h0/intermediate/after arrival, route selection switch | Backend positions invert checkpoint elapsed-distance pairs, lie on actual geometry, clamp origin/destination; selected marker matches route/frame and is labeled estimated, no new ETA/domain calculation in React; no new provider/HTTP calls |
| HEAT-10 | Combined/wind/rain/snow at same frame; measure full compressed payload with/without hazard arrays | <=500 KB including all metadata/profiles/positions permits codes/control; otherwise capabilities.hazard_filter=false, codes/control omitted and combined remains; codes match real backend independent hazards/load-adjusted wind, UNKNOWN visible; no changes to ETA weather/ranking; zero filter HTTP |

## SIM: deterministic scenario weather, identity and real pipeline

RECOMMENDATION | D24 tests use the actual scenario weather adapter plus recorded distinct routing/geocode fixtures and frozen departure. Presets never bypass risk/aggregation/ranking or fabricate route results. Choose fixture geometries that intersect the deterministic weather fields to demonstrate each branch; arbitrary live routes need not yield the same winner. Weather at identical coordinate/time is identical across route memberships and independent of load.

| ID | Given/action | Expected evidence |
|---|---|---|
| SIM-01 | Absent/null preset; config disabled; valid enabled preset; unknown preset | Live default and false/null identity; disabled/unknown gets safe400 before provider work; only explicit enabled valid selection uses simulation. SIMULATION_ENABLED defaults false; no silent fallback on live failure |
| SIM-02 | Simulated success, provider error, partial/stale snapshot, older response after new live request; cache same coordinates live vs scenario | Every simulated analysis response/error propagates true/preset; persistent SIMULATION banner and scenario-name badge remain on map/cards/details/slider/errors; atomic replacement, no mixed source data or cache hit; live identity false/null |
| SIM-03 | All clear with unequal-duration distinct route fixtures | All checkpoints Low, average1, Severe/High/No Travel0; fastest complete route wins via normal fourth criterion; banner says All clear |
| SIM-04 | High-wind corridor35/45 mph with loads exactly/just over40000/30000, lower-wind segments elsewhere | 35 mph: High at40000, Severe above;45 mph: Severe at30000, No Travel above. Weather unchanged by load; final maxima and known block eligibility use real rules; corridor fixture with an unblocked alternative wins over blocked |
| SIM-05 | Winter storm field intersects snow rates .5/1/2.5 in/hr; fixture A fewer Severe miles but slower than B | Moderate/High/Severe snow rendered and owned miles verified; A wins on Severe despite later disadvantages; snow depth/hour, not water equivalent; actual comparison explanation |
| SIM-06 | Heavy rain front liquid rates .10/.25/.75 in/hr with controlled distinct geometry fixtures | Moderate/High/Severe rain; equal Severe but fewer High wins. A second equal-Severe/High fixture with different Low/Moderate ownership wins on lower average even when slower; real mile totals/facts, no scenario ranking special case |
| SIM-07 | Blocked trip with wind55 everywhere on all fixture routes | All contain No Travel for every valid load; recommended_route_id=null; least_blocked_route_id follows No Travel miles then normal tie criteria; explicit no-safe-route warning and SIMULATION labels |
| SIM-08 | Tie-break uniform Moderate weather on unequal-duration routes; then equal-duration distinct routes in all permutations | Equal Severe/High/average; shortest duration wins first fixture, canonical geometry ID wins exact tie; actual tie explanation and stable identity; no cloned geometry |
| SIM-09 | Same normalized observation fixtures through live fixture adapter and scenario adapter; change load, scenario or mode | Same interface/schema/domain functions yield same results for same inputs; scenario weather invariant under load, all real risk layers preserved, no metric/ordering shortcuts; zero live weather calls in simulation, routing still counted |
| SIM-10 | Deterministic real Django/browser journey through six presets and return to live fixtures | Persistent flag/banner/badge and intended risk/branch assertions for each preset; partial-data fixtures additionally cover UNKNOWN exclusion; not interception of final response; label routing/geocode fixture evidence, no live-weather dependency; configuration disabling rejects selector requests |

## Performance, end-to-end, hosting, delivery

| ID | Check | Evidence required |
|---|---|---|
| PERF-01 | 300-point/49-frame scrub on documented desktop browser/device | Measure actual request count, frame p50/p95 and long tasks; target p95<=16.7 ms, no sustained>50 ms task; record missed targets honestly, not a guessed60fps |
| PERF-02 | Production build and compressed response | Actual gzip JS/chunk sizes and analysis payload; target initial JS<=200 KB excluding lazy map and typical response<=500 KB compressed; no recreated map or unrelated card/form commits during scrub |
| PERF-03 | Short/long trip, cold/warm server, failed provider | Actual observed latency including wakeup, total warm 35 s deadline, progress/cancel responsiveness; don't invent a universal provider latency guarantee |
| PERF-04 | Playback/filter/truck marker/profile/theme/motion interactions, new analysis and unmount | Same D23 frame/network/payload limits; no unrelated card/form commits during playback, no leaked timers/listeners; hazard filter cut when payload fails; P2 motion introduces no layout shift, reduced-motion honored |
| E2E-01 | Playwright with real frontend/Django and injected provider fixtures | Fill trip -> choose geocoding -> submit -> three real fixture routes/reason -> marker details -> scrub0/24/48; assert visible time, synchronized state, request count; save screenshots |
| E2E-02 | Deterministic blocked and partial-data journeys | Null recommendation and explicit warnings; no missing=Low or unlabelled fake success; simulation mode persistently labeled when used in demo |
| E2E-03 | Separate optional live provider smoke and hosted manual browser | One actual live trip plus map/markers/slider rendering and no-scrub requests; do not describe intercepted fixtures as live provider verification |
| E2E-04 | Actual scenario adapter with real Django + injected routing/geocode fixtures and browser preset selector | SIM-01..10 flag propagation/banner/scenario assertions, intended risk and recommendation branches, switch mode/replace/cancel without mixing; screenshot six labeled presets; simulated evidence never presented as live |
| DEPLOY-01 | Production Django config and real endpoints | DEBUGFalse, strict hosts/CORS, env secrets, HTTPS/proxy/static serving, health/validation/analysis HTTP behavior; actual output inspected |
| DEPLOY-02 | Production frontend request destination/CORS preflight | Calls actual production backend, no localhost/key in bundle, successful/failed preflight origins correct |
| DEPLOY-03 | Host idle cold start and unavailable backend | Clear waking status, bounded recovery/retry, useful failed state; no hidden keepalive automation |
| DEPLOY-04 | Hosted desktop/mobile trip and slider | Live three-route corridor, recommendation/checkpoint detail, forecast endpoints and attribution; recorded network/screenshots; local success alone insufficient |
| DEPLOY-05 | Provider and hosting quota/license gates | Free-only access verified, current terms/attribution/account controls confirmed, no-charge controls; unverified gate remains a declared launch blocker |
| DEPLOY-06 | Account/plan access and server simulation enable/disable | No card-required or paid provider/host; stop/report if required. TomTom live gate failure stops for user choice (ORS100 km not drop-in); no plaintext credentials in chat; simulation disabled by configuration without affecting live default |
| DEL-01 | GitHub repository and clean reproducible setup | Accessible repo, small coherent commits, correct Windows/local and Linux/host docs, safe env example; no secrets; dependency/license audit actually run |
| DEL-02 | README | Live URLs, screenshot, architecture, exact PDF table plus approved interpretation, risk/ranking explanation, env/API/setup/tests, limits/known issues/future work |
| DEL-03 | Loom | Actual 5-10 min recording: inputs/live route comparison/map/slider, severe or blocked labeled simulation, one passing ranking test, architecture/tradeoffs; URL accessible |
| DEL-04 | Final submission check | Relevant tests/lint/types/build output inspected, hosted check performed, published URLs verified; failures/skips/incomplete requirements named explicitly |

## Execution order and truthful results

- RECOMMENDATION | Start RISK/MET/RANK offline; then ROUTE/CP/WX fixtures; then API; then UI/MAP/HEAT; then full browser and performance; finally hosted/live verification and delivery. Every meaningful implementation task consults its cases before editing and reruns checks justified by changed layers.
- RECOMMENDATION | Inject recorded/minimal deterministic HTTP response fixtures for adapters. Browser journey uses a real Django service with fixture adapters, not only interception of the final analysis response, so orchestration and frontend are exercised together. Basemap/map rendering must be visually checked independently of API mocks.
- RECOMMENDATION | During later development run actual project commands for backend pytest/Ruff/mypy; frontend non-watch tests/ESLint/tsc/production build; Chromium Playwright and dependency audit before submission. The foundation now provides dev.py and verified Windows commands in AGENTS section10; see foundation.md. Full trip/hosted/provider checks remain later work.
- UNVERIFIED | Execution record at approval stage: no application tests, lint, type-check, build, browser journey, dependency audit or deployment has run. Only documentation/source inspection and contract checks apply to this task. Live quota/access evidence, all executable acceptance tests and measured performance remain UNVERIFIED.

## Foundation execution record (2026-10-10)

These criteria were added for the explicitly authorized foundation task; earlier feature specifications remain unimplemented unless stated here.

| ID | Criterion | Evidence/result |
|---|---|---|
| FND-01 | Locked setup in project envs, no map/global dependency, spaced paths | setup exit0; 32 Python/191 npm packages; dependency inventory |
| FND-02 | Stateless independent health, version/status/readiness, correct method error | 3 backend health tests; actual HTTP200 liveness/readiness/CORS |
| FND-03 | Env-driven config, loud production missing-secret failure, strict origins/hosts | 10 config/startup tests passed; no real .env/secret created |
| FND-04 | Pure domain boundary without feature logic | 2 guard tests; AST check passes on empty domain package |
| FND-05 | Shell loading/healthy/unreachable and non-watch tests | 3 Vitest tests; real Chromium smoke1passed; screenshot inspected |
| FND-06 | Backend/frontend lint, format, strict types, artifacts | Ruff/ESLint/mypy/tsc/Django/Vite all exit0; details foundation.md |
| FND-07 | Valid Linux CI with exact case and a spaced checkout | JSON-form YAML syntax and local command/path checks pass; Linux run UNVERIFIED |
| FND-08 | Safe local-only Git, PDF preserved/ignored, no staged secrets/artifacts | Final staged review/clean local commit reported with task; no remote/push |
| FND-09 | Exact license/purpose/size inventory and advisory tools | dependencies.md; OSV32/0affected, npm0vulnerabilities |

See [foundation.md](foundation.md) for failures corrected, skipped Linux/hosted/feature checks and actual outputs. This does not satisfy API-01 route-analysis or E2E-01 full trip journey.
