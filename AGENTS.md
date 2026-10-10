# AGENTS.md — RouteShield (Weather-Aware Truck Routing)

> Working product name: RouteShield, approved 2026-10-10.
> This file is read at the start of every session. Follow it exactly. Keep it
> current: when a command, path, or decision here becomes wrong, fix it in the
> same change.

---

## 0. How to work with me (read first)

- This is a hiring assessment for a Full Stack Developer role at Spotter AI.
  Passing it decides the next hiring stage. Treat every task as if a senior
  reviewer will read the code, run the app, and watch the demo.
- Hard budget: **4 calendar days / 16 working hours total**, including planning.
  The user reports elapsed time; never invent hours, deadlines or a balance.
  Never expand scope. Polish and correctness beat features. The PDF says: *"Prioritize correctness and
  clarity over extra features."*
- Work **one feature per task**. For anything larger than a small fix, first
  write a short plan (files to touch, approach, tests), then implement.
- Follow APPROVED/CHANGED decisions in `docs/decisions.md` and its frozen contract.
  If a new material ambiguity changes correctness and is not settled there,
  mark it OPEN, ask at most three specific questions and stop dependent work.
  Never turn a proposed entry or undocumented default into approval.
- Planning is closed (2026-10-10). The next phase is implementation, **one
  focused user-issued task at a time**. Approval of the plan does not start
  implementation automatically; respect each task's allowed files/actions.
- Never invent the content of a doc this file references. If a referenced doc
  is missing, say so and create it only when the task asks for it.
- Never claim a test, build, lint, browser check, push, or deployment passed
  unless you actually ran it and inspected the output. Report failures and
  skips honestly.
- Keep diffs small and scoped. Do not rewrite unrelated working code.
- Do not add a dependency without stating why, what it replaces, and its
  license/size impact.

---

## 1. Mission and scoring

Build a polished, reliable React + Django web app that helps a truck driver
choose the safest route based on **weather, load weight, and travel time**.

Evaluation weights (spend effort proportionally):

| Weight | Area |
|-------:|------|
| 40% | Routes, weather, risk and recommendation logic (correctness) |
| 35% | UI, map and heatmap smoothness and performance |
| 10% | Code quality |
| 5%  | Documentation and walkthrough |

The printed weights total **90%**. Do not normalize them or invent a missing
10% category. React and Django are the only mandated technologies; the rest
of the stack below is an approved engineering choice.

Deliverables: GitHub repository, hosted application, 5–10 min Loom walkthrough.

### Required behavior (from the assessment PDF)

User enters: origin and destination, departure date/time, load weight.

The app must:

1. Generate **3 route options** using a routing API.
2. Sample weather every **10 / 25 / 50 miles** using the truck's **estimated
   arrival time at each checkpoint**.
3. Calculate weather risk using the provided risk and load rules.
4. Recommend the best route, balancing weather risk and travel time.
5. Show all routes, checkpoints, risk levels, ETAs, and route summaries on a map.
6. Show a **weather heatmap along the trip corridor** with a **0–48 hour
   forecast slider**.

Third-party APIs are allowed. A custom routing engine is **not** needed.

---

## 2. Source of truth and precedence

Order of authority when sources conflict:

1. The assessment PDF (`Requirements/fs-assessment-spotter.pdf`) — requirements and thresholds.
2. `docs/decisions.md` — dated APPROVED/CHANGED decisions and frozen contract.
3. This file.
4. `docs/requirements-traceability.md` — requirement → code → test mapping.
5. `docs/acceptance-tests.md` — consult **before** implementing and **before**
   declaring any feature done.

Rules:

- Never silently change thresholds, ranking priorities, or units.
- Distinguish **explicit requirements**, **approved decisions**, and
  **assumptions** in code comments, docs, and your reports.
- If the PDF and any other source disagree, the PDF wins; tell me.
- PROPOSED/OPEN entries never authorize implementation. An UNVERIFIED external
  fact remains an evidence gate even when the policy itself is approved.

---

## 3. Domain specification (PDF transcription plus approved conventions)

Printed tables and load operators below are PDF requirements. The ordinal
scale, continuous boundaries, combining hazards, intervals, mile ownership,
timing, UNKNOWN/blocking and heatmap semantics are approved choices D01-D10,
not additional printed PDF statements. Full records: `docs/decisions.md`.

### 3.1 Printed risk and load rules

| Condition | Low | Moderate | High | Severe | No Travel |
|-----------|-----|----------|------|--------|-----------|
| Wind (mph) | <25 | 25–34 | 35–44 | 45–54 | ≥55 |
| Rain (in/hr) | <0.10 | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | >1.00 |
| Snow (in/hr) | <0.5 | 0.5–1.0 | 1.0–2.0 | 2.0–3.0 | >3.0 |

- Wind ≥55 mph -> No Travel for any load.
- Wind45–54 mph and load >30000 lb -> No Travel.
- Wind35–44 mph and load >40000 lb -> Severe.

### 3.2 Approved boundaries and combination (D01-D03, D08)

- Continuous wind: Low <25; Moderate [25,35); High [35,45);
  Severe [45,55); No Travel ≥55. Apply the same continuous wind windows to
  load rules; load comparisons are strictly >30000 and >40000.
- Rain: Low <.10; Moderate [.10,.25); High [.25,.50);
  Severe [.50,1.00]; No Travel >1.00.
- Snow depth: Low <.5; Moderate [.5,1); High [1,2);
  Severe [2,3]; No Travel >3. Exactly1.00 rain/3 snow remain Severe.
- No rounding before classification; one named backend threshold table.
- Sustained non-gust 10 m wind classifies risk; optional gust display cannot
  affect classification or make otherwise complete data UNKNOWN.
- Ordinals LOW1 < MODERATE2 < HIGH3 < SEVERE4 < NO_TRAVEL5.
  Independently classify wind/rain/snow, retain individual and maximum
  hazard risk, separately load-adjusted wind, then final maximum and reasons.
- A missing required metric means final UNKNOWN, with no ordinal; preserve
  known hazard floor and known No Travel evidence. Missing is never Low.
  UNKNOWN miles are separate; incomplete routes have null full average,
  remain visible, unranked and ineligible for recommendation.

### 3.3 Checkpoints, ownership and ETAs (D04, D06)

- Checkpoints follow provider-calibrated distance along real geometry,
  including origin0 and destination once, never straight-line distance.
- Common interval: user10/25/50 mi; adaptive default by longest accepted
  route ≤100mi:10, ≤500mi:25, else50. Cap-driven increase to the next
  offered interval must warn; if50 cannot fit mandatory points, fail
  TRIP_TOO_LARGE. Coarsen extra display samples before mandatory checkpoints.
- ETA = departure + interpolated cumulative provider time, preferring
  aligned vertex distance/time; valid guidance anchors are a fallback.
  Invalid/missing timing is an error, never guessed constant speed.
- UTC instants internally; input includes ISO offset and visibly named IANA
  zone, checked for DST gaps/repeated times and consistency. Checkpoint local
  display uses provider IANA metadata with explicit UTC fallback.
  No rest/fuel stops or live traffic model; disclose continuous driving.
- Checkpoint owns distance between adjacent midpoints; endpoints own half
  the neighbor segment. [0,10,20,23] -> [5,10,6.5,1.5] owned miles.
  Category totals are exact and disjoint, including UNKNOWN; known block
  evidence overlapping UNKNOWN is diagnostic, never double-counted.
- Complete-route average = sum(owned miles * ordinal)/route miles,
  unrounded until display. Incomplete full average is null.

### 3.4 Recommendation (D07-D08; lexicographic)

- Known No Travel blocks regardless of other missing metrics.
- Complete nonblocked routes rank ahead of every blocked route, by:
  Severe miles, High miles, average risk, duration, stable canonical ID.
- Complete blocked routes compare No Travel miles first, then those criteria.
  Incomplete routes are never ranked or recommended.
- All blocked: recommended_route_id=null; separate least_blocked_route_id
  only from complete diagnostics, with "No safe route at this departure
  time and load". Never call a blocked diagnostic recommended.
- Mixed blocked/incomplete without proof every route is blocked:
  "No fully assessed travelable route", not a false all-blocked assertion.
- Explain the actual deciding comparisons, exclusions and exact ties.
  Never weighted sums, rounded ranking keys or hardcoded winner reasons.

### 3.5 Weather, units and hourly lookup (D03, D05, D11-D12)

- Open-Meteo primary; access/use eligibility, attribution, required variables
  and horizon are later verified gates, not approval claims.
- Explicit mph/inch request; independently validate unit metadata.
  Liquid rain = rain + showers; missing either is unknown, not zero.
  Snowfall is snow depth, never snow water equivalent/total precipitation.
- Convert accumulation depth to inches and divide by interval hours for
  in/hr (mm/25.4; cm/2.54); preserve source components and hourly-average
  uncertainty. Reject negative/nonfinite/unknown-unit observations.
- Select row t whose accumulation interval (t-1h,t] contains ETA:
  12:20 ->13:00; exactly13:00 ->13:00. Expose row/wind timestamp.
  No nearest-hour substitution or category interpolation.
- Fetch through ceil(max(departure+48h, latest ETA)); absent/out-of-horizon
  data is unavailable, never extrapolated or rounded into coverage.
- Pool/batch coordinates per D21; successful normalized weather TTL≤15min,
  source/model/coords/window/variables/units keys; risk caches also load/policy.

### 3.6 Real routing and distinctness (D09)

- TomTom Routing + Geocoding primary: truck mode, maxAlternatives2,
  anyRoute, full geometry, extended cumulative distance/travelTime vertices;
  validate summary alignment and monotonic timing. Cargo is not gross truck
  weight; do not invent tare/dimensions or pass cargo as gross restriction.
- First live gate must confirm free/no-card access, truck alternatives and
  usable cumulative timing. If it fails, STOP and ask before switching.
  ORS driving-hgv is the approved conditional fallback, with a100km native
  alternatives cap; it is not a general long-haul replacement.
- Distinctness: resample geometry every0.5mi with length ownership;
  match within100m of the other polyline, symmetric overlap = maximum of
  directional covered-length ratios; reject >90%, exactly90% allowed.
  Sort stable geometry IDs before filtering.
- Bounded waypoint fallback: at most2 real provider calls, same endpoints/
  profile, within shared deadline; discard duplicate/no-route results.
  Fallback search detour cap1.5x fastest native duration is not a ranking key.
- Never fabricate/clone routes. Fewer than3 -> truthful count/warning,
  not full PDF fulfillment; zero -> NO_ROUTE. Verified demo needs3 distinct.

### 3.7 Corridor forecast and permitted controls (CHANGED D10)

- Pool all returned routes' centerlines, mandatory checkpoints first,
  extra display samples initially10mi and coarsened; dedupe within100m,
  ≤300 unique points pending D21 quota gate. Show actual spacing.
- Return h0..48 (49 frames), departure-relative with absolute time/zone.
  All risk codes computed by the same Python risk rules and load.
  Arrival-time risk/recommendation stays fixed while corridor time changes.
- One cached analysis response to browser, bounded upstream batches.
  Zero initiated HTTP requests on scrub/play/filter at fixed viewport.
- Five constant-hue category layers; density controls opacity only, never
  severity. UNKNOWN gray/pattern and known-block evidence remain visible;
  exact labeled points above blur. No unmeasured off-road safety claim.
- Permit explicit play/pause, never autoplay; discrete frames, stop at48,
  pause on manual scrub/new analysis/unmount; honor reduced motion.
- Selected-route estimated truck marker: backend positions derived from
  existing checkpoint ETAs and chainage, clamped origin/destination; frontend
  displays them without ETA/position domain calculations or new calls.
- Optional combined/wind/rain/snow filter uses returned backend codes
  (wind is load-adjusted). Include codes/control only if full compressed
  response ≤500KB; otherwise capabilities.hazard_filter=false and omit it.

---

## 4. Approved architecture, stack and API

Keep these boundaries strict:

- Frontend presents/selects backend results; no risk, ranking, forecast
  lookup, ETA or estimated-position domain logic in TypeScript.
- Domain is pure Python: classification/load, chainage/checkpoints,
  ownership/aggregation/ranking, corridor frames/positions. No Django/HTTP.
- Provider adapters isolate geocoding/routing/weather shapes, units, errors
  and deterministic scenario weather behind the same weather interface.
- Thin DRF API validates, orchestrates, serializes and maps errors.

Approved primary stack D13-D19 (alternatives require documented eligibility
and user direction where specified; they never authorize silent substitution):

- Backend: Python3.12+, Django, DRF, dataclasses, synchronous HTTPX with
  timeouts/bounded I/O, django-cors-headers; pytest/pytest-django, Ruff,
  mypy/django-stubs. Stateless; no app database models.
- Frontend: React + strict TypeScript, Vite, plain CSS, TanStack Query and
  local reducer/state; MapLibre GL JS + OpenFreeMap; Vitest/Testing Library,
  ESLint/tsc, Playwright. No UI/chart/motion library.
  MapLibre is approved for a later map task and is not installed in the foundation.
- Hosts: Cloudflare Pages static frontend; Render Free Django with Linux
  Gunicorn/WhiteNoise. No paid/card-required service; no keepalive pings.
- D19 before dependencies: exact pinned versions/licenses, purpose/replacement
  and measured size impact; no guessed size/license claims.

Foundation layout below exists; comments naming risk, adapters, maps or trips
describe future work. Domain/provider packages contain no feature logic yet.

```
/Requirements
  fs-assessment-spotter.pdf
/backend
  /config
  /apps/routing          # thin API, serializers, service orchestration
  /domain                # risk, checkpoints, aggregation, ranking, corridor
  /providers             # geocoding, routing, weather, scenario_weather
  /tests                 # recorded fixtures; pure/adapter/API tests
  requirements.in        # exact approved direct pins
  requirements.lock      # complete Python environment pins, including pip
  pyproject.toml
  .env.example           # safe documented examples only
/frontend
  /src
    /api                 # one shared typed contract/client
    /components          # map, cards, legend, slider, profile, source labels
    /features            # trip/results/heatmap; local selection/play state
    /lib                 # formatting/time/unit display only
  /e2e                   # live health browser smoke, not the trip journey
  package.json
  package-lock.json
  .env.example           # public API base URL only
/tools                   # domain import, CI and staged-file checks; OSV audit
/.github/workflows       # Linux CI, spaced checkout path
/docs
  decisions.md
  requirements-traceability.md
  acceptance-tests.md
  architecture.md
  plan.md
  dependencies.md
  foundation.md          # verified foundation usage and evidence
dev.py                   # single entry point; explicit venv, argument lists
README.md
```

### Public API (full schema in docs/architecture.md)

- POST /api/v1/route-analysis/: origin/destination Place objects, ISO-offset
  departure_time, IANA departure_timezone, load_weight_lb; optional
  checkpoint_interval_miles and simulation_scenario (absent/null = live).
- Returns identity/freshness/trip, routes with geometry/distance/duration,
  checkpoints with ETA/weather/all risk layers, summaries/risk_profile,
  nullable recommended_route_id and least_blocked_route_id, explanation/
  comparison facts, warnings/attributions; is_simulation/simulation_scenario;
  corridor points/49 frames with per-route truck_positions and conditional
  hazard_codes; capabilities.hazard_filter controls filter availability.
- GET /api/v1/geocode/?q=: Place candidates (client debounced400ms, min3 chars).
- GET /api/v1/health/: provider-independent liveness, version/status/check;
  ?ready=1 reports process/configuration readiness only, no quota/database call.
- Errors: {error:{code,message,details}}, correct HTTP status, no client trace.
  All simulated analysis successes/errors include is_simulation=true and
  simulation_scenario; live analyses/errors false/null.
- No added endpoint for slider/play/filter/simulation; all forecast interaction
  uses the same payload. Versioned/validated/typed API; optional OpenAPI only
  within the existing timebox.

---

## 5. Reliability and external APIs

- Validate every external response; handle missing, null, or malformed fields.
- D21: ≤300 pooled locations, ≤50/batch, ≤2 concurrent; connect3s,
  routing read12s, weather/geocode read8s, total warm35s deadline, ≤1 transient
  retry with capped backoff; fallback calls count toward the same deadline.
- Apply timeouts, **bounded** retries with backoff, and clear user-facing
  errors for provider failure, rate limiting, and no-route-found.
- Respect provider quotas, licensing, and attribution (display required
  attributions in the UI footer).
- No shared routing/geocode cache until provider storage terms permit it.
  Successful normalized weather uses exact coordinate/window/model/unit/source
  keys and ≤15min TTL; risk caches include load/policy. Never cache errors as
  successes or share live/scenario entries.
- Never fabricate weather, routes, or success responses. Mocks and fixtures
  are for tests and an explicitly labeled demo mode only.
- Clearly label stale, unavailable, or out-of-horizon data in the UI.
- D24 simulation: live default; SIMULATION_ENABLED defaults false. Six explicit
  deterministic weather presets: All clear, High-wind corridor, Winter storm,
  Heavy rain front, Blocked trip, Tie-break; same weather interface and real
  risk/aggregation/ranking, no score overrides. Weather stays independent of
  load; real routing in the app, separately labeled recorded routes in tests.
- Never silently mix live/scenario weather, including partial/cache/stale data.
  Every simulated analysis success/error carries true/preset identity; preserve
  persistent SIMULATION banner and named badge throughout results/errors.
  Explicit re-analysis changes mode; config can disable it.
- Do not market the app as a certified or guaranteed safety system; include a
  short, visible advisory disclaimer.

---

## 6. Frontend and UX quality (35% of the grade)

- One consistent design system: typography scale, spacing scale, and fixed
  **risk-color semantics** (Low → Severe → No Travel) used identically in
  map, legend, cards, and charts. Do not rely on color alone — add icons,
  labels, or patterns.
- Make the **recommendation and why** understandable within seconds of
  results loading.
- Map shows all three routes (distinct styling, selectable), checkpoints with
  risk markers, ETA and weather on selection, and a legend. Selecting a route
  in the list highlights it on the map and vice versa; forecast time, route
  selection, and checkpoint details stay **synchronized**.
- Implement real **loading, empty, error, partial-data, and unavailable**
  states. No spinners that never resolve; no silent failures.
- Responsive from narrow mobile to wide desktop. Keyboard-accessible controls,
  visible focus states, meaningful labels, sufficient contrast, reduced-motion
  respect.
- No decorative controls that do nothing. No placeholder/lorem content.
- **Performance budgets** (verify and report real numbers):
  - Slider scrub stays smooth (target 60 fps; no network calls; no full
    re-render of unrelated components).
  - Memoize derived map data; update map layers/sources incrementally instead
    of recreating the map.
  - Lazy-load heavy map code; keep the initial bundle lean.
  - Typical trip analysis should feel responsive; show progress for slow
    provider calls and never block the UI thread.
- CHANGED D22 P2: system/manual light-dark theme with CSS variables/plain CSS,
  refined system typography; optional one self-hosted variable font only after
  license/size checks. No UI kit.
- P2 restrained route reveal, staggered results, fixed-width one-time count-up,
  bounded existing-map camera easing, skeletons, selection transitions.
  CSS/Web Animations DOM effects use transform/opacity only, no layout shift;
  reduced motion is immediate/static. No motion library without D19 justification.
- P2 selected-route distance-risk strip/SVG reads backend midpoint segments;
  no chart library or frontend risk rules. Cut P2 work first at missed gates
  using the exact order in docs/plan.md.
- Measure D23 targets: ≤500KB compressed analysis including new fields,
  initial JS≤200KB gzip excluding lazy map; scrub p95≤16.7ms and no sustained
  >50ms tasks on recorded hardware/browser. Targets are not claimed passes.

---

## 7. Deployment and operations

- Configuration via environment variables only. Maintain a safe
  `.env.example` with every variable documented. No secrets in Git, ever.
- Production settings: `DEBUG=False`, strict `ALLOWED_HOSTS`, explicit CORS
  origins, HTTPS, secure cookie flags where applicable, static files served
  correctly (e.g. WhiteNoise), gunicorn (or equivalent).
- Free-only/no required card. Stop and tell the user if a provider/host requires
  payment/card; no auto-upgrade. User creates TomTom key and Cloudflare/Render
  accounts later; never request plaintext keys in chat, use local .env/dashboard.
- Free-tier cold starts: provider-independent health, accessible waking UI
  with bounded polling/retry ≤90s, and user-triggered pre-demo warmup only.
  No keepalive pings to defeat sleep; disclose cold starts in README.
- Verify the **hosted** app end to end (not just local) before calling the
  deployment done. Confirm the production frontend actually reaches the
  production backend.
- Add CI (lint, type-check, tests, build) if it costs under ~20 minutes;
  a green badge in the README helps.

---

## 8. Code quality

- Follow existing repository conventions before introducing new patterns.
- Small, cohesive modules; descriptive names; no premature abstraction.
- Python: type hints everywhere, `ruff` clean, `mypy` clean. Use
  standard dataclasses for domain objects (D15); no added Pydantic layer. No magic numbers —
  thresholds live in one named, documented table.
- TypeScript: `strict` on, no `any` without a justifying comment, shared API
  types in one place.
- Validate input at system boundaries (API serializers, form validation).
- Business logic is deterministic and free of I/O.
- Remove dead code, debug prints, commented-out code, and unused dependencies
  before finishing a task.
- Comments explain **why**, not what. Public functions get concise docstrings.

---

## 9. Testing and verification

- Read the relevant acceptance criteria before implementing.
- **Domain logic gets exhaustive unit tests**: every threshold boundary for
  every hazard, every load rule (including exactly 30,000 and 40,000 lb and
  exactly 55 mph), combined hazards, UNKNOWN weather, mile attribution,
  average risk, ranking priority order, ties, and all-blocked routes.
- Use deterministic recorded fixtures or mocks for provider tests; never hit
  live APIs in unit tests. Keep one small, clearly marked, optional
  live-provider smoke test.
- Test API validation failures, provider timeouts, malformed responses, and
  out-of-horizon forecasts.
- Frontend: component tests for risk legend, route list/selection, slider
  behavior, and error states; one Playwright end-to-end flow (enter trip →
  see 3 routes → recommendation → move slider).
- Run checks relevant to changed layers after each meaningful implementation
  change; inspect output. Documentation-only tasks use document/reference/
  contract checks, and explicitly skip nonexistent application checks.
- Exercise the real browser UI for key flows; confirm map, markers, and slider
  actually render and respond. Take screenshots when verifying UI changes.
- Verify API behavior with real requests, not only that the server starts.
- D24 deterministic browser tests exercise the actual scenario weather adapter
  plus recorded routing/geocode fixtures, six intended risk/comparison scenarios,
  flag/banner propagation and live/scenario isolation. These are not live API
  evidence. Consult SIM-01..10 and E2E-04 before implementing.

---

## 10. Commands

Run from the repository root. Prerequisites: Python3.12+ and Node24/npm already
installed. First setup uses the available Python to create backend/.venv;
all subsequent commands use that interpreter explicitly, without activation.
Setup, all commands below and the explicit Windows interpreter were executed
and inspected on Windows in a path containing a space. Linux counterparts are
wired into CI; Linux execution/hosting remains UNVERIFIED until CI runs.

First setup: PowerShell `python "./dev.py" setup`; Linux `python3 "./dev.py" setup`.
Repeated setup: use the venv interpreter with `"./dev.py" setup`.
Stop both dev servers before setup; Windows locks native Node modules in use.

| Goal / tools | PowerShell from repository root | Linux from repository root |
|---|---|---|
| Both servers: Django + Vite | `& "./backend/.venv/Scripts/python.exe" "./dev.py" run` | `"./backend/.venv/bin/python" "./dev.py" run` |
| Tests: pytest + non-watch Vitest | `& "./backend/.venv/Scripts/python.exe" "./dev.py" test` | `"./backend/.venv/bin/python" "./dev.py" test` |
| Lint/format check: Ruff + ESLint + domain boundary | `& "./backend/.venv/Scripts/python.exe" "./dev.py" lint` | `"./backend/.venv/bin/python" "./dev.py" lint` |
| Format: Ruff + ESLint fixes | `& "./backend/.venv/Scripts/python.exe" "./dev.py" format` | `"./backend/.venv/bin/python" "./dev.py" format` |
| Types: strict mypy/django-stubs + tsc | `& "./backend/.venv/Scripts/python.exe" "./dev.py" typecheck` | `"./backend/.venv/bin/python" "./dev.py" typecheck` |
| Build: Django check/static/compile + tsc/Vite | `& "./backend/.venv/Scripts/python.exe" "./dev.py" build` | `"./backend/.venv/bin/python" "./dev.py" build` |
| Project-local Chromium download | `& "./backend/.venv/Scripts/python.exe" "./dev.py" browser-install` | `"./backend/.venv/bin/python" "./dev.py" browser-install` |
| Live health browser smoke (servers running) | `& "./backend/.venv/Scripts/python.exe" "./dev.py" e2e` | `"./backend/.venv/bin/python" "./dev.py" e2e` |
| Published advisory audit: OSV + npm | `& "./backend/.venv/Scripts/python.exe" "./dev.py" audit` | `"./backend/.venv/bin/python" "./dev.py" audit` |
| CI syntax/command/path validation | `& "./backend/.venv/Scripts/python.exe" "./dev.py" ci-check` | `"./backend/.venv/bin/python" "./dev.py" ci-check` |

Check commands accept `--only backend` or `--only frontend`. Browser downloads,
venv, npm installation and caches stay inside the project. Ctrl+C stops both
owned dev servers. Gunicorn is installed for later Linux hosting, not used on
Windows; production bind/worker settings await deployment. Do not run installs
or setup in a documentation-only task without user authorization.

---

## 11. Security and privacy

- Never commit API keys, tokens, passwords, or production credentials.
  `.env*` stays out of Git except `.env.example`.
- Provider credentials live on the server; never in frontend bundles.
- Validate and constrain user input (coordinate ranges, weight ranges,
  date ranges, string lengths). D21 per-IP analysis10/10min, geocode30/min
  plus global quota guard; DRF throttles are best effort, not DoS protection.
  First feasibility spike MEASURES one uncached300-coordinate Open-Meteo
  analysis; >100 quota units -> propose lower cap/get user direction BEFORE
  API orchestration. Missing evidence does not permit a guessed cost/cap.
- Return safe error messages; never leak stack traces, keys, or internals.
- Do not log secrets or unnecessary personal data.
- Keep dependencies minimal and current; run a dependency audit before
  submitting.
- Do not run destructive commands or make consequential external changes
  (force-push, deleting branches, rotating keys, changing hosting config)
  without explicit authorization.

---

## 12. Git and change management

- When Git is authorized, check `git status` before changing/committing files.
  A task prohibiting Git operations overrides this rule; do not run Git then.
- Work in small, reviewable milestones with clear commit messages
  (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). Use feature branches when
  helpful.
- Never overwrite unrelated user work. Never commit a broken state as a
  completed milestone.
- Commit history should read like a professional build log.
- Never claim to have pushed or deployed unless the operation succeeded.

---

## 13. Explicitly out of scope (do NOT build)

Authentication and user accounts, saved trips, databases of historical data,
multi-stop routing, real-time traffic, push notifications, ML-based risk
prediction, admin dashboards, i18n, payments, and a custom routing engine.
Approved D10/D22 P2 refinements and D24 labeled simulation are permitted within
plan.md's existing timeboxes; this does not authorize extra features.
If an idea is not in the PDF or approved decisions and does not directly
improve correctness, clarity, or the 35% UI/performance score, skip it and note it under "Future
work" in the README.

---

## 14. Time budget (4 calendar days / 16 working hours)

Allocations include planning; actual elapsed time comes only from the user.
Full suballocations, gates and exact cut order: docs/plan.md.

| Milestone | Hours | Cumulative |
|---|---:|---:|
| M0 planning/review/approval | 1.25 | 1.25 |
| M1 scaffold/production skeleton | 0.50 | 1.75 |
| M2 risk/miles/ranking with tests | 2.25 | 4.00 |
| M3 routing/checkpoints/ETAs | 1.50 | 5.50 |
| M4 weather/frames | 1.00 | 6.50 |
| M5 API orchestration | 0.50 | 7.00 |
| M6 form/results | 1.50 | 8.50 |
| M7 map/selection + P2 theme/profile | 1.00 | 9.50 |
| M8 heatmap/slider + P2 playback/truck marker | 1.00 | 10.50 |
| M9 integration/tests/defects + D24 simulation | 2.00 | 12.50 |
| M10 hosted deployment/verification | 1.25 | 13.75 |
| M11 README/submission/Loom | 1.50 | 15.25 |
| Reserve: defects + conditional P2 | 0.75 | 16.00 |

Protected gates: usable API payload7h; complete local journey10.5h;
hosted journey13.75h. If missed, cut remaining P2 in order: optional font,
hazard filter, motion/camera/skeleton refinement, risk profile, theme toggle/
dark theme, playback/truck marker; then optional tooling/gusts if still needed.
Keep accessible base styles/loading/selection, real heatmap/slider, D24 source
labels/real pipeline, domain correctness, deployment and Loom. No mandatory
requirement is silently dropped. Report gaps and ask for direction if cutting
P2 is insufficient. Never invent an overrun or claim a gate passed.

---

## 15. Documentation deliverables

- **README.md**: what it does, screenshot/GIF, live URL, architecture
  diagram, tech choices and why, how risk and recommendation work (with the
  threshold table and boundary conventions), assumptions and limitations,
  setup and run instructions, test commands, env vars, API summary, known
  issues, and future work.
- `docs/decisions.md`: frozen contract and each decision's context/options,
  APPROVED/CHANGED/OPEN status, user reasoning/date, choice and consequence.
  Architecture/traceability/acceptance/plan must agree with the contract.
- The README doubles as the **Loom script**: cover the problem, live demo
  (including a persistently labeled simulated blocked/severe scenario and the slider), the recommendation
  logic with a test shown passing, architecture, and trade-offs, within
  5–10 minutes.

---

## 16. Definition of done

A task is complete only when:

1. Its approved requirements are implemented.
2. Relevant acceptance criteria are satisfied.
3. Relevant checks were executed and their results inspected: tests/lint/
   type-check/build for changed application layers, document/reference/contract
   checks for documentation-only work. State all skipped checks explicitly.
4. No regression was found in the checks performed.
5. Errors and unavailable-data states are handled.
6. Documentation and this file are updated where behavior, setup, or
   decisions changed.
7. The final response lists: what changed (files), what was tested and how,
   what failed or was skipped, assumptions made, and what remains incomplete.

If a requirement cannot be completed within budget, report it explicitly
instead of disguising a partial implementation as finished.
