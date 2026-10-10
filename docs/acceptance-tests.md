# RouteShield acceptance and boundary tests

RECOMMENDATION | Status: APPROVED SPECIFICATION, 2026-10-10. Implementation and execution evidence is recorded only in the dated sections below; a specification alone is not a passing test. Numerical interpretations follow [decisions.md](decisions.md). Use fixed fixtures, injected provider clients, and a frozen clock; ordinary tests prohibit outbound routing/weather/geocode calls. Planned file paths are in [requirements-traceability.md](requirements-traceability.md).

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
| RISK-07 | Provider rain/showers/snow/wind components each null/missing/malformed separately | Adapter marks the affected normalized hazard unavailable; pure domain consumes combined rainfall, not rain/showers components. None gives UNKNOWN and retains known evidence. Invalid normalized numbers raise a domain validation error; component parsing belongs to adapter tests |
| RISK-07 | Every nonempty missing-hazard subset, including all three absent; missing wind with heavy cargo | Final/hazard level UNKNOWN; individual known levels and known floor retained (none if no evidence), block flag retained; missing wind has an explicit load-rules-unavailable reason |
| RISK-07 | Cargo None with otherwise complete weather, including wind >=55 | No implicit zero cargo; final UNKNOWN, known hazard floor retained. Extreme wind still proves No Travel for any cargo and keeps known_blocked=true |
| RISK-08 | Every normalized hazard and cargo given a negative, NaN/infinity, boolean, string or complex value | DomainValidationError with field and stable validation code; None alone means missing, not malformed |
| RISK-08 | Cargo 0,100000,100000.0001; 30000.5/40000.5 and arbitrarily small exact Decimal excesses | Inclusive D20 limits; reject excess beyond maximum; preserve decimal cargo and strict load comparisons without integer coercion |
| RISK-09 | Decimal sums reaching .10,.25,.50,1.00; float boundary literals and adjacent representable floats | Exact Decimal sums reach their bands; canonical float decimal text is compared without quantization/epsilon; an already computed below/above-boundary float stays there |
| RISK-10 | Repeat inputs under different Decimal contexts; mutate result/reason/band/policy; import in isolated interpreter | Equal deterministic results, immutable evidence and policy, no framework/network imports; existing AST purity guard still passes |

IMPLEMENTATION | Numeric input contract: use Decimal for exact source values and arithmetic in future adapters. Integers convert exactly; floats convert with Decimal(str(value)), using their shortest round-trip decimal representation. Literal float 0.1 therefore compares at the decimal 0.10 boundary. There is no fixed precision, rounding, quantization, or epsilon adjustment in classification. The intended decimal sum cannot be recovered from a float already affected by binary arithmetic: ten sequential float additions of 0.05 produce 0.49999999999999994, which remains High; the corresponding exact Decimal sum is 0.50, which is Severe. Future adapter arithmetic must use adequate Decimal precision before passing normalized inputs; the engine itself only compares and does not depend on the caller's Decimal context.

IMPLEMENTATION | The module accepts normalized sustained wind mph, combined liquid rainfall in/hr, snow-depth in/hr, and cargo pounds only. Gusts, unit conversions, provider components, timestamps and transport data do not enter this interface. Missing cargo follows this task's None-is-missing convention and yields an incomplete final assessment; this adds no invented cargo value or hazard. UNKNOWN has no ordinal. Its known_risk_floor is evidence, never a substitute for a complete final assessment; known_blocked=false on incomplete data is not proof that travel is safe.

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
| ROUTE-02 | TomTom lat/lon plus normalized vertex cumulative distance/time or geometry-indexed sparse progress; valid guidance fallback; ORS GeoJSON/steps in separate adapter fixtures | Canonical [lon,lat], meters, seconds; validated sparse progress expands onto vertices using traveled geometric chainage, with timing source exposed; monotonic guidance fallback is announced; missing/invalid timing fails safely; no swapped hemisphere. JSON/request parsing and ORS integration remain adapter work |
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

## Pure risk engine execution record (2026-10-10)

Only risk classification, wind/load rules and normalized-input validation were implemented in this task. No dependency was added. The frozen contract remains unchanged.

| Criteria | Executable evidence | Result |
|---|---|---|
| RISK-01..03 | backend/tests/test_risk_boundaries.py: all printed endpoints at -0.0001/exact/+0.0001, wind fractions, strict rain/snow cutoffs | Passed |
| RISK-04 | Same file: requested 36-case load/wind matrix, existing acceptance 77-case matrix, wind55/zero cargo | Passed |
| RISK-05 | backend/tests/test_risk_results.py: all 125 hazard combinations, explicit combined/load examples, all three load-reason codes and comparison evidence | Passed |
| RISK-07 | Same file: all seven missing-hazard subsets, all-low known floors, known hazard/load blocks, missing-wind and missing-cargo explanations | Passed at the normalized domain boundary; provider component parsing remains future adapter work |
| RISK-08..10 | backend/tests/test_risk_validation.py and test_risk_results.py: field-specific errors, exact decimal cargo, boundary float neighbors/sums, context independence, immutable results/policy and isolated runtime import | Passed |
| Domain purity | Existing backend/tests/test_domain_boundary.py plus tools/check_domain.py | Both guard tests passed; four domain files have no forbidden imports |
| Existing startup safety | backend/tests/test_environment.py production fixture now explicitly sets DEBUG=false | Prevents a user's local development .env from changing the missing-secret assertion; all ten config/startup tests passed |

Verified commands from the repository root in PowerShell (explicit project interpreter; quoted spaced paths):

```powershell
& "./backend/.venv/Scripts/python.exe" "./dev.py" test --only backend
& "./backend/.venv/Scripts/python.exe" "./dev.py" lint --only backend
& "./backend/.venv/Scripts/python.exe" "./dev.py" typecheck --only backend
& "./backend/.venv/Scripts/python.exe" "./dev.py" build --only backend
```

- Tests: exit0, **438 passed**, including **423 new risk cases** and 15 existing foundation cases.
- Lint/format/purity: exit0, Ruff clean, 29 Python files already formatted, four domain files checked.
- Strict type check: exit0, mypy found no issues in 27 source files.
- Backend build: exit0, Django system check found no issues, static collection completed, configuration/API/domain/provider packages compiled.
- Corrected during verification: a test incorrectly relied on the older float sum() algorithm; it now uses explicit sequential addition. The full suite exposed the existing production fixture's inherited DEBUG value, corrected above. Test import formatting and deliberate invalid-comparison type annotations were also fixed before the passing runs. No outstanding failure in the performed checks.
- Skipped: frontend tests/lint/types/build and browser checks (no frontend change); HTTP/live-provider checks, dependency audit (no dependency change), Linux CI and deployment. RISK-06's optional-gust adapter/UI journey, provider component parsing, checkpoints/ETA/mile attribution, aggregation/ranking and integration remain later tasks. This record does not claim those specifications pass.
- Documentation follow-up: AGENTS.md section4 still describes the domain as having no feature logic. That foundation-status sentence needs a later update because AGENTS.md is outside this task's authorized edit paths; this execution record states the implemented domain status.

## Geometry, checkpoints and aggregation execution record (2026-10-10)

IMPLEMENTATION | This task authorizes pure geometry/checkpoint/aggregation code and representation of the observed provider shape; it does not authorize provider parsing, network work, ranking, changes to AGENTS.md or the frozen contract. The provider spike's proposed lower cap is not applied: the default remains 300. No dependency was added; Fraction, dataclasses and zoneinfo are standard-library modules, using the foundation's existing timezone data.

### Distance, timing and interpolation contract

- Provider summary distance is authoritative for route length, checkpoint spacing and exact owned/category mileage. Validated provider cumulative distance/time anchors are authoritative for ETA on that same calibrated chainage. Geometric traveled chainage locates and interpolates coordinates within each segment. Coordinates are canonical WGS84 longitude/latitude; meters and seconds remain internal units.
- build_route accepts aligned vertex distance/time arrays or normalized sparse point-index/distance/time anchors matching the synthetic progress fixtures and provider-findings.md. Sparse anchors expand by geometric distance within each supplied anchor span. The output vertex arrays align to collapsed geometry. Input arrays must align to original geometry before duplicate collapse.
- Both the whole route and every timing-anchor span must satisfy abs(provider_distance - geometric_distance) <= geometry_absolute_tolerance_m + geometry_relative_tolerance * geometric_distance. A mismatch is a typed failure; the two distance sources are never silently substituted. Reconciliation tolerances below are explicit implementation defaults, not additional frozen decisions or measurements of a provider guarantee.
- Timing indexes/distances/times must be finite, valid, non-decreasing, start at vertex0/distance0/time0, and reach the final vertex and summary totals. Endpoint discrepancies within the configured meter/second tolerances are snapped to summary totals with TIMING_ENDPOINT_RECONCILED. Original monotonicity is checked before snapping. Invalid primary timing uses validated guidance only, exposing GUIDANCE_TIMING_FALLBACK and the rejected code; neither valid means NO_VALID_TIMING. Supplied endpoint-only anchors are an explicit interpolation span; absent timing never manufactures a speed estimate.
- Coordinates use spherical minor-great-circle interpolation on the actual selected polyline segment, with mean Earth radius below. Antimeridian and polar arcs are handled by 3D vectors. Near-antipodal segments are rejected as AMBIGUOUS_SEGMENT. Road-scale accuracy depends on the provider polyline's vertex quality: the method follows each supplied arc and does not reconstruct unsampled road curvature. Synthetic equatorial/meridian/polar/antimeridian controls pass at 1e-9 degrees or better; independent ellipsoidal geodesic accuracy has not been measured. The sphere's distance approximation motivates the configurable 1% plus 5m reconciliation allowance.
- Consecutive geometric spans within duplicate_point_tolerance_m collapse to zero, with point-index remapping and all timing/wait anchors retained. Exact interior checkpoint chainage uses first arrival; interpolation beyond it includes the provider's subsequent stationary wait. Origin elapsed remains0 and destination elapsed remains total duration. A positive distance on stationary geometry, or moving geometry with zero provider chainage, is unmappable and fails. Coordinate reversals and loops are valid traveled paths; latitude/longitude are not sorted.
- Departure must be timezone-aware and is normalized to UTC; nonexistent ZoneInfo wall times fail. Each checkpoint can attach its own IANA zone; missing/invalid names explicitly yield UTC with a warning. Exact elapsed seconds remain Fraction; datetime ETAs use native microsecond resolution (nearest microsecond, ties to even), including any sub-microsecond interpolation. Driver breaks are not invented.

### Interval, ownership and summary contract

- One common interval applies to all accepted routes. The adaptive default uses the longest route: <=100mi ->10, <=500mi ->25, otherwise50. A valid user choice takes precedence. Mandatory count is ceil(route_miles / interval_miles)+1 per route, summed before allocation. This is a conservative upper bound; the later weather task owns cross-route coordinate deduplication within100m.
- If the count exceeds the budget, select_interval moves only to the next offered interval and returns CHECKPOINT_INTERVAL_INCREASED with old_interval_miles and new_interval_miles for each step. If the largest interval still fails, TRIP_TOO_LARGE is returned. generate_trip_checkpoints applies that plan to every route. Direct single-route generation is also bounded and requires an already suitable interval.
- Fraction arithmetic preserves input Decimal/Fraction values exactly; floats use their canonical decimal text. Ownership boundaries are0, adjacent checkpoint-distance midpoints andL, converted using the exact meter/mile scale. Every interval is disjoint and their lengths telescope exactly toL, including short routes and short final segments. No display rounding enters mileage or averages.
- Aggregation accepts generated checkpoints and existing risk-engine results. Final LOW/MODERATE/HIGH/SEVERE/NO_TRAVEL categories and unknown_miles form one exact partition. average_risk is the exact mile-weighted ordinal mean only with complete data; otherwise null. known_only_average_risk_diagnostic uses complete final observations only and never supplies a missing full average or ranking input; no ranking is implemented here.
- maximum_known_level and known_risk_floor both expose the highest proven level, including an UNKNOWN checkpoint's floor, or none without evidence. no_travel_checkpoint_count/no_travel_miles count final NO_TRAVEL only. known_blocked_checkpoint_count and known_blocked_miles_diagnostic retain proof overlapping UNKNOWN as separate diagnostics, never extra category miles. Any known block yields BLOCKED; otherwise missing data yields INCOMPLETE; otherwise ASSESSED. known_blocked=false is absence of proven block, not a claim that an incomplete route is unblocked. Coverage is exact known-final mileage divided by route mileage.

### Complete RoutePolicy parameters and defaults

| Parameter | Default | Authority/purpose |
|---|---|---|
| offered_intervals_miles | (10,25,50) | D04 required offered choices |
| adaptive_thresholds_miles | (100,500) | D04 longest-route thresholds, inclusive |
| checkpoint_budget | 300 | Frozen D21; per-route mandatory count upper bound |
| meters_per_mile | 1609.344 exactly (201168/125) | D04 exact conversion |
| earth_radius_m | 6371008.8 | Mean-radius spherical geometry implementation |
| geometry_absolute_tolerance_m | 5 | Absolute reconciliation allowance |
| geometry_relative_tolerance | 0.01 | Geometric-distance-relative reconciliation allowance |
| distance_endpoint_tolerance_m | 1 | Maximum summary/anchor distance endpoint discrepancy |
| time_endpoint_tolerance_s | 1 | Maximum summary/anchor elapsed endpoint discrepancy |
| duplicate_point_tolerance_m | 0.001 | Consecutive coincident-point collapse tolerance |
| antipodal_tolerance_radians | 1e-9 | Reject minor-arc ambiguity near pi radians |

Policies are immutable and validated, and every route in a trip must share one policy. Tests supply changed intervals, adaptive thresholds, budget, conversion, geometry tolerances, radius, endpoint tolerances, duplicate tolerance and antipodal tolerance to verify these are parameters rather than buried logic. WGS84 bounds, midpoint division by2 and microseconds/second are mathematical/unit definitions rather than adjustable product limits.

### Executed versus planned acceptance coverage

| Existing ID | Test group/file | Current status |
|---|---|---|
| CP-01,CP-02 | test_checkpoints.py: short/exact/final segments, all offered intervals, endpoint coordinates | EXECUTED/PASS at pure domain boundary |
| CP-03 | Same file: longest-route thresholds, explicit choice, common trip plan, one/double budget bump and largest-interval failure | EXECUTED/PASS; weather coordinate pooling remains PLANNED |
| CP-04 | test_geometry.py: unequal speeds, sparse progress expansion, endpoint values | EXECUTED/PASS with supplied provider timing |
| CP-05 | Same file: full/per-span reconciliation, duplicate/wait preservation, loops, invalid arrays/indexes/coordinates/totals/geometry, guidance fallback | EXECUTED/PASS; provider JSON validation remains PLANNED |
| CP-06 | test_checkpoints.py: UTC/local midnight, different checkpoint zones, DST spring/repeat/gap, UTC fallback, naive input errors | EXECUTED/PASS; API input offset/name consistency validation and provider timezone metadata remain PLANNED |
| MET-01 | Same file: golden100/105mi cases, [0,10,20,23], short routes, generated rational/Decimal conservation | EXECUTED/PASS with exact equality |
| MET-02 | test_route_aggregation.py: owned [5,10,6.5,1.5], category totals, exact66/23 mean | EXECUTED/PASS |
| MET-03 | Same file: unknown6.5mi, coverage16.5/23, null full mean, diagnostic46.5/16.5, UNKNOWN known block and all-UNKNOWN | EXECUTED/PASS; recommendation exclusion is later RANK work |
| MET-04 | Same file: five disjoint final levels, unknown partition, all offered intervals, uniform routes, immutable summaries | EXECUTED/PASS |
| ROUTE-01 | test_geometry.py synthetic fixture helper preserves canonical geometry/summary/progress shape | PARTIAL/EXECUTED; outgoing requests, truck profile preservation, attribution and provider parsing PLANNED |
| ROUTE-02 | Same file: aligned/sparse timing, guidance recovery, missing both, canonical coordinate fixture helper | PARTIAL/EXECUTED normalized model; TomTom/ORS adapters and provider JSON parsing PLANNED |
| ROUTE-06 | Same file: malformed normalized geometry/summary/timing and typed errors | PARTIAL/EXECUTED domain validation; HTTP failures/retries/cache/API mapping PLANNED |
| ROUTE-03..05,ROUTE-07 | Distinctness, bounded real alternatives/no-route, live truck access | PLANNED application work; historical spike evidence is not a domain/adapter test |

Verified PowerShell commands from the repository root, with the existing explicit project interpreter and quoted paths:

```powershell
& "./backend/.venv/Scripts/python.exe" "./dev.py" test --only backend
& "./backend/.venv/Scripts/python.exe" -m pytest "./backend/tests/test_geometry.py" "./backend/tests/test_checkpoints.py" "./backend/tests/test_route_aggregation.py"
& "./backend/.venv/Scripts/python.exe" "./dev.py" lint --only backend
& "./backend/.venv/Scripts/python.exe" "./dev.py" typecheck --only backend
& "./backend/.venv/Scripts/python.exe" "./dev.py" build --only backend
```

Inspected final output excerpts (all commands exit0):

```text
Full backend suite: 630 passed
New geometry/checkpoint/aggregation cases: 192 passed
Ruff: All checks passed!
Ruff format: 38 files already formatted
Domain boundary: 9 files checked; no forbidden imports.
Strict mypy: Success: no issues found in 36 source files
Backend build: System check identified no issues (0 silenced).
```

Static collection and package compilation also completed successfully. No application test failed during this task; initial formatting findings and six test-only type-check errors were corrected (Fraction expectations and deliberately invalid policy arguments). No outstanding failure or regression was found in the performed checks.

Skipped: frontend tests/lint/types/build, browser checks, HTTP/live-provider checks, dependency audit, Linux CI execution and deployment. These layers/dependencies were not changed; ROUTE adapter, RANK recommendation, weather pooling and application integration acceptance remain planned as mapped above. AGENTS.md and docs/decisions.md were not edited, as explicitly required by this task. The local staged-file/secret review and final commit/clean-tree result are reported with the task.

## Route ranking and explanations execution record — 2026-10-10

IMPLEMENTED | This record supersedes earlier statements that domain RANK work or MET-03 recommendation exclusion is planned. Application/API/browser integration remains planned. Only backend/domain, backend/tests and this document changed; no dependency was added. Frozen decisions, architecture and AGENTS.md were not edited.

### Exact eligibility and ordering

`recommend_routes` consumes `RankingInput(route, summary)` using the existing normalized Route and RouteSummary. It does not classify weather or recalculate aggregates. Every numerical key is the original Fraction returned by aggregation; no float conversion, display rounding or epsilon enters comparison.

| Group | Eligibility and exact ascending key |
|---|---|
| ASSESSED | Complete, no known block: `(severe_miles, high_miles, average_risk, duration_seconds, stable_route_id)` |
| BLOCKED_COMPLETE | Complete, known block: `(no_travel_miles, severe_miles, high_miles, average_risk, duration_seconds, stable_route_id)` |
| UNRANKED | Any incomplete route, including travel_status BLOCKED: no numerical key or rank; stable ID order is presentation only |

Every ASSESSED row precedes every BLOCKED_COMPLETE row. Ranked rows have consecutive one-based ranks across those two groups. UNRANKED rows retain their travel_status, known_blocked, unknown_miles, coverage_fraction and null average. The known-only diagnostic average is never read by ranking. Contradictory/nonexact aggregates fail INVALID_ROUTE_SUMMARY; zero routes fail the existing NO_ROUTE code.

`decisive_criterion` compares the recommended route with its next ASSESSED competitor: SEVERE_MILES, HIGH_MILES, AVERAGE_RISK, DURATION or TIE_BROKEN_BY_ID; NONE when no such pair exists. A blocked diagnostic has no recommendation winner, so its separate `diagnostic_decisive_criterion` may be NO_TRAVEL_MILES or one of those five criteria, otherwise null. This separates the task's six recommendation criterion codes from blocked ordering. Each comparison fact gives both raw values at the first differing criterion. Cross-group exclusion uses ELIGIBILITY with both group strings, never an incomplete mean.

When present, comparison_facts use the recommendation as winner, otherwise the complete least-blocked diagnostic. Every other route gets a fact, including an eligibility exclusion for incomplete data. With neither selected ID, comparison_facts is empty and all routes still expose coverage and reasons. A least-blocked diagnostic is exposed only when no eligible recommendation exists and is explicitly not recommended.

### Status codes and exact message fields

| recommendation_status | Exact message |
|---|---|
| RECOMMENDED | Recommended fully assessed route |
| BEST_FULLY_ASSESSED_AVAILABLE | Best fully assessed available route |
| ALL_BLOCKED | No safe route at this departure time and load |
| NO_FULLY_ASSESSED_TRAVELABLE_ROUTE | No fully assessed travelable route |
| ALL_INCOMPLETE | All routes have incomplete weather data |

At least two assessed routes use RECOMMENDED. Exactly one assessed route always uses BEST_FULLY_ASSESSED_AVAILABLE, including a lone returned route, with availability/coverage disclosures. ALL_BLOCKED requires known blocking evidence on every route, including incomplete ones; the rendered explanation explicitly says this is based on the assessed data. A diagnostic can only come from complete blocked rows. All-incomplete routes with some, but not universal, known blocking evidence use NO_FULLY_ASSESSED_TRAVELABLE_ROUTE under D08; all-incomplete with no evidence use ALL_INCOMPLETE. No blocked or incomplete route receives recommended_route_id.

### Identity and presentation conventions

IMPLEMENTATION CHOICE | `stable_route_id` returns `route_` plus the full SHA-256 hex digest of versioned ASCII `route-geometry-v1|lon,lat;lon,lat;...`. Values are signed integer microdegrees, longitude first, rounded half-even to six decimal coordinate places from exact Fraction(canonical float text). Signed zero becomes0. Quantization is exclusively for identity. Original coordinates and all comparison values remain unchanged. Canonical Route geometry already removes consecutive duplicate vertices; traveled point order and vertex density are preserved, so reversing a path changes its ID. Coordinate mapping key order and provider alternatives order do not affect identity. Distinctness/resampling remains provider-task work. A duplicate/colliding quantized ID raises DUPLICATE_ROUTE_ID instead of introducing input-order dependence.

IMPLEMENTATION CHOICE | English mileage/time values use2 decimal places (time in minutes), mean risk3 and percentage coverage1, using exact rational half-even display rounding. If a decisive raw numeric difference disappears in display, prose states "Raw values differ; displayed values are rounded." Only exact numerical equality reaches identifier tiebreak prose. The presentation-only closeness policy emits LOWER_PRIORITY_DURATION_CLOSE for `0 < abs(duration difference) <= 240 seconds` when No Travel/Severe/High/average already decided the comparison. Its text says duration did not decide; the note never changes ordering. Equal times or a duration-decided comparison do not emit it.

### Structured fields and names requiring approval

The API's existing routes, route_count, recommended_route_id, least_blocked_route_id, recommendation_status, explanation and comparison_facts names are retained. Existing aggregation/status/criterion units are reused. There is no serialization or API endpoint in this task; a later serializer must preserve raw comparison precision.

| Object | Complete implemented field inventory |
|---|---|
| RankingInput | route, summary |
| CriterionValues | no_travel_miles, severe_miles, high_miles, average_risk, duration_seconds, stable_route_id |
| RankedRoute | route_id, group, rank, travel_status, known_blocked, criteria, unknown_miles, coverage_fraction |
| ComparisonFact | winner_route_id, other_route_id, criterion, winner_value, other_value, code |
| ExplanationFact | code, route_id, other_route_id, values |
| Recommendation | routes, route_count, recommended_route_id, least_blocked_route_id, recommendation_status, message, decisive_criterion, diagnostic_decisive_criterion, comparison_facts, explanation_facts, explanation |

New structural field names whose detailed shape was not defined in architecture.md, listed for user approval: **route, summary, group, rank, criteria, winner_route_id, other_route_id, criterion, winner_value, other_value, code, values, message, decisive_criterion, diagnostic_decisive_criterion, explanation_facts, duration_difference_seconds**. Some words appear conceptually in the contract; this is a conservative inventory of the newly specified structures. Values-map keys are winner_value, other_value, route_count, coverage_fraction, unknown_miles, known_blocked (boolean), duration_difference_seconds; numbers remain exact Fraction/int. Generated dataclasses, tuples and values mappings are immutable.

New naming choices include RECOMMENDED for normal status, BLOCKED_COMPLETE for the complete blocked group and ELIGIBILITY for exclusion comparisons. Other recommendation status names came directly from this task. Error codes added internally: INVALID_ROUTE_SUMMARY, DUPLICATE_ROUTE_ID, INCOMPLETE_AVERAGE (defensive key guard).

Complete explanation-code inventory (every template executed): **RECOMMENDED, BEST_FULLY_ASSESSED_AVAILABLE, ALL_BLOCKED, NO_FULLY_ASSESSED_TRAVELABLE_ROUTE, ALL_INCOMPLETE, SEVERE_MILES, HIGH_MILES, AVERAGE_RISK, DURATION, TIE_BROKEN_BY_ID, NO_TRAVEL_MILES, PARTIAL_ROUTES, ASSESSED_BEFORE_BLOCKED, INCOMPLETE_UNRANKED, LEAST_BLOCKED_DIAGNOSTIC, LOWER_PRIORITY_DURATION_CLOSE**. All status/warning/comparison text is generated in Python from these facts. Coverage disclosures retain known blocking evidence even for unranked rows.

### Executed versus planned acceptance coverage

| Existing ID | Tests/evidence | Current status |
|---|---|---|
| RANK-01 | test_ranking.py: three-route Severe adversary, extra .001mi defeats hours saved/fewer High, sub-display difference | EXECUTED/PASS |
| RANK-02 | Same: equal Severe, fewer High defeats lower mean/hours, sub-display difference | EXECUTED/PASS |
| RANK-03 | Same: equal Severe/High, mean1.01 beats1.02/1.03 despite hours, sub-display difference | EXECUTED/PASS |
| RANK-04 | Same + test_route_identity.py: exact time, sub-display time, six three-route ties, 24 permutations for each of three four-route scenarios, directed geometry/key-order/half-even identity | EXECUTED/PASS; provider response parsing remains PLANNED |
| RANK-05 | test_ranking.py: assessed Severe90/mean3.7 precedes blocked .001mi/mean1.00004, group-valued facts | EXECUTED/PASS |
| RANK-06 | Same + test_recommendation_explanations.py: No Travel10/15/20 order, all remaining blocked priorities/id, exact message, complete-only diagnostic with unknown peers | EXECUTED/PASS |
| RANK-07 | Both files: known-only mean1 excluded against complete3.7, partial known block, mixed/all-incomplete/all-known-blocked, one/two/three/zero options | EXECUTED/PASS |
| RANK-08 | test_recommendation_explanations.py: every code/template, raw facts for every competitor, exact tie vs display tie, eligibility/coverage, bounded lower-priority duration note | EXECUTED/PASS at pure domain boundary; UI rendering PLANNED |
| MET-02, MET-04 | test_ranking.py: retains exact aggregate Fractions by identity; real aggregate integration; previous aggregation tests rerun | EXECUTED/PASS |
| MET-03 | Both files: incomplete means remain null/uncompared, known blocks retained, coverage/unknown facts | EXECUTED/PASS at aggregation/ranking boundary; API serialization PLANNED |
| UI-02 | Actual recommendation/comparison text/facts generated and asserted | PARTIAL/EXECUTED domain explanation; visual clarity/cards/map interaction PLANNED |
| UI-04 | Exact blocked/incomplete/availability/coverage text and null IDs asserted | PARTIAL/EXECUTED domain states; visible UI, horizon/stale rendering PLANNED |

### Commands and inspected output

Run in PowerShell from the quoted repository root, using the project's own interpreter:

```powershell
& "./backend/.venv/Scripts/python.exe" "./dev.py" test --only backend
& "./backend/.venv/Scripts/python.exe" -m pytest "./backend/tests/test_ranking.py" "./backend/tests/test_route_identity.py" "./backend/tests/test_recommendation_explanations.py"
& "./backend/.venv/Scripts/python.exe" "./dev.py" lint --only backend
& "./backend/.venv/Scripts/python.exe" "./dev.py" typecheck --only backend
& "./backend/.venv/Scripts/python.exe" "./tools/check_domain.py"
& "./backend/.venv/Scripts/python.exe" "./dev.py" build --only backend
```

Also executed from backend: `& "./.venv/Scripts/python.exe" -m mypy --strict --config-file "./pyproject.toml" "./domain"`.

Inspected final outputs (all exit0):

```text
Full backend: 787 passed
New ranking/identity/explanation tests: 157 passed
Ruff: All checks passed!
Ruff format: 46 files already formatted
Strict mypy, full backend/tooling: Success: no issues found in 44 source files
Strict mypy, domain only: Success: no issues found in 13 source files
Domain boundary: 13 files checked; no forbidden imports.
Backend build: System check identified no issues (0 silenced).
Static collection: 0 copied, 27 unmodified, 49 post-processed.
Package compilation: completed, exit0.
```

Initial findings corrected before these final checks: Ruff formatting/import order/line length; two strict-mypy findings (test sum inferred int/float and fixed-length comparison tuple annotation); one new integration test fixture passed Fraction to the existing Decimal/int/float risk input API, corrected to Decimal. No outstanding failure or regression in the performed checks.

Skipped: frontend/browser/HTTP/provider checks, dependency audit, Linux CI execution and deployment because those layers/dependencies were unchanged and outside this task. API serialization, provider parsing/distinctness, application integration and visual acceptance remain incomplete. Staged-file review, the single local commit and clean-tree confirmation are reported in the final task report; no remote or push is authorized.
