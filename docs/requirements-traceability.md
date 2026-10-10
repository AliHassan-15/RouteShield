# RouteShield requirements traceability

RECOMMENDATION | Status: APPROVED SPECIFICATION, 2026-10-10; every implementation location below is planned, not existing code. All acceptance IDs resolve in [acceptance-tests.md](acceptance-tests.md). Source is `../Requirements/fs-assessment-spotter.pdf`, fully inspected pages 1-2. Interpretation choices are separated in [decisions.md](decisions.md); execution sequence is [plan.md](plan.md).

RECOMMENDATION | Priority P0 = required assessment behavior or correctness gate; P1 = essential supporting reliability/clarity; P2 = optional refinement within budget. Priority is engineering judgment, not an additional assessment weight. Acceptance criteria are approved and executable tests remain unimplemented/unexecuted.

## Explicit PDF requirements

| ID / label | PDF source and requirement | Planned implementation location | Acceptance IDs | Priority / test method |
|---|---|---|---|---|
| PDF-01 REQUIREMENT | p1: React + Django application | `frontend/src/App.tsx`; `backend/config/`; API app | API-01; E2E-01; DEPLOY-01 | P0 / stack inspection, real HTTP/browser journey |
| PDF-02 REQUIREMENT | p1: Origin and destination input | `frontend/src/features/trip/TripForm.tsx`; `backend/apps/routing/serializers.py`; geocoding adapter | API-02; API-07; UI-01 | P0 / API/component and deterministic geocode fixtures |
| PDF-03 REQUIREMENT | p1: Departure date/time input | Trip form/serializers; `backend/domain/checkpoints.py` | API-03..04; CP-06; WX-03 | P0 / offset/DST/frozen-clock tests |
| PDF-04 REQUIREMENT | p1: Load weight input | Trip form/serializers; `backend/domain/risk.py` | API-03; RISK-04 | P0 / input and strict-threshold tests |
| PDF-05 REQUIREMENT | p1: Generate three route options with routing API | `backend/providers/routing.py`; `backend/apps/routing/service.py` | ROUTE-01..07; E2E-01; DEPLOY-04 | P0 / recorded three-route fixtures plus separately observed live three-route trip |
| PDF-06 REQUIREMENT | p1: Sample every 10/25/50 miles | `backend/domain/checkpoints.py` | CP-01..03; MET-01 | P0 / synthetic along-geometry distance tests for all intervals |
| PDF-07 REQUIREMENT | p1: Weather uses estimated arrival at each checkpoint | Checkpoints; weather adapter; service | CP-04..06; WX-03..05 | P0 / unequal segment times, timestamp/horizon fixtures |
| PDF-08 REQUIREMENT | p1: Wind Low <25, Moderate 25-34, High 35-44, Severe 45-54, No Travel >=55 mph | `backend/domain/risk.py`; named threshold table | RISK-01; RISK-06 | P0 / every printed endpoint plus approved fractional gaps |
| PDF-09 REQUIREMENT | p1: Rain Low <.10, Moderate.10-.25, High.25-.50, Severe.50-1.00, No Travel>1.00 in/hr | Risk module; weather-unit adapter | RISK-02; WX-01..03 | P0 / every endpoint; correct liquid-rain normalization |
| PDF-10 REQUIREMENT | p1: Snow Low <.5, Moderate.5-1.0, High 1.0-2.0, Severe 2.0-3.0, No Travel>3.0 in/hr | Risk module; weather-unit adapter | RISK-03; WX-02 | P0 / every endpoint; snow depth versus water-equivalent fixture |
| PDF-11 REQUIREMENT | p2: Wind >=55 mph -> No Travel any load | Risk module | RISK-04..05 | P0 / exact 55 and all load combinations |
| PDF-12 REQUIREMENT | p2: Wind 45-54 mph and load >30000 lb -> No Travel | Risk module | RISK-04 | P0 / below/equal/above load and wind boundaries |
| PDF-13 REQUIREMENT | p2: Wind 35-44 mph and load >40000 lb -> Severe | Risk module | RISK-04 | P0 / below/equal/above load and wind boundaries |
| PDF-14 REQUIREMENT | p2: Prefer fewest Severe miles first | `backend/domain/aggregation.py`; `recommendation.py` | MET-01..04; RANK-01 | P0 / first criterion defeats every later advantage |
| PDF-15 REQUIREMENT | p2: Fewest High miles second | Aggregation/recommendation | RANK-02 | P0 / equal Severe case |
| PDF-16 REQUIREMENT | p2: Lowest average risk third | Aggregation/recommendation | MET-02..03; RANK-03 | P0 / approved distance weighting; equal Severe/High |
| PDF-17 REQUIREMENT | p2: Shortest travel times fourth | Recommendation; provider durations | RANK-04; CP-04 | P0 / all preceding values equal |
| PDF-18 REQUIREMENT | p1: Map shows all routes | `frontend/src/components/RouteMap.tsx` | MAP-01..02; E2E-01 | P0 / actual map screenshot and selection |
| PDF-19 REQUIREMENT | p1: Map shows checkpoints and risk levels | RouteMap; `RiskLegend.tsx` | MAP-01..03; RISK-05 | P0 / visible markers/segments/legend and backend values |
| PDF-20 REQUIREMENT | p1: Map shows ETAs and route summaries | `CheckpointDetails.tsx`; map-linked summary overlays | MAP-01..02; CP-06 | P0 / actual popup/sidebar synchronized with map |
| PDF-21 REQUIREMENT | p1: Weather heatmap along trip corridor | `backend/domain/corridor.py`; map heat layers | HEAT-01; HEAT-04..06 | P0 / weather-changing frames and real overlay screenshot |
| PDF-22 REQUIREMENT | p1: 0-48 h forecast slider | Corridor frames; `HeatmapSlider.tsx` | HEAT-01..03; HEAT-07; E2E-01 | P0 / all 49 offsets, labels and actual interaction |
| PDF-23 REQUIREMENT | p2: GitHub repository | Future repository root/README and authorized Git milestones | DEL-01; DEL-04 | P0 / actual accessibility, reproducible setup; no Git initialized in Phase0 |
| PDF-24 REQUIREMENT | p2: Hosted application | Future deployment config/env settings/frontendAPI URL | DEPLOY-01..05 | P0 / actual production API/browser/cold-start evidence |
| PDF-25 REQUIREMENT | p2: 5-10 minute Loom walkthrough | Future README walkthrough sequence and recording | DEL-02..03 | P0 / actual accessible recording and measured duration |
| PDF-26 REQUIREMENT | p2: Prioritize correctness and clarity over extra features | Task scope and fixed schedule | DEL-04; plan milestone gates | P0 / review unfinished requirements and cuts before enhancements |

REQUIREMENT | The PDF permits third-party routing/geocoding/weather and says a custom routing engine is unnecessary. These are scope permissions, not extra deliverables. The approved adapter design uses them without building an engine.

## Evaluation mapping

| Label | Printed evaluation area | Supporting implementation/evidence | Planning treatment |
|---|---|---|---|
| REQUIREMENT |40% routes/weather/risk/recommendation | PDF-05..17; RISK/CP/MET/RANK/ROUTE/WX/API cases | Core logic+integrations prioritized; deterministic boundary and live integration evidence |
| REQUIREMENT |35% UI/map/heatmap smoothness/performance | PDF-18..22; UI/MAP/HEAT/PERF/E2E | Protected map/slider work plus measured performance and visual inspection |
| REQUIREMENT |10% code quality | Domain/adapter/API separation, typed contract; relevant lint/types/tests | Continuous quality, small modules, no hidden business rules in React |
| REQUIREMENT |5% documentation/walkthrough | PDF-23..25; DEL-01..04 | Protected README/Loom slot with actual run/deploy evidence |

REQUIREMENT | Printed weights total90%. No fifth category or missing10% allocation is invented; approved planning preserves the printed weights.

## Approved engineering policies and supporting acceptance

RECOMMENDATION | The rows below are not additional PDF statements. Each follows its APPROVED/CHANGED decision; these make required behavior precise or reliable. D10/D22 refinements are P2 and have explicit missed-gate cuts; D24 simulation is a user-approved supporting requirement.

| ID / label | Policy and decision | Planned location | Acceptance IDs | Priority / test method |
|---|---|---|---|---|
| POL-01 RECOMMENDATION | Continuous gaps/shared boundaries; D01 | Backend risk table | RISK-01..04 | P0 / all exact/fractional cases |
| POL-02 RECOMMENDATION | Maximum hazards, separate load result, sustained wind, ordinal scale; D02 | Domain risk/models | RISK-05..07 | P0 / combined/gust/unknown fixtures |
| POL-03 RECOMMENDATION | Rain+showers, snowfall depth, hourly rate conversion; D03 | Weather adapter | WX-01..03; RISK-02..03 | P0 / metadata and unit-equivalence fixtures |
| POL-04 RECOMMENDATION | Adaptive/selectable common intervals and ETA chainage; D04 | Checkpoints/routing adapter | CP-01..06; ROUTE-02 | P0 / provider timing mapping and bounds |
| POL-05 RECOMMENDATION | Enclosing hourly interval and real horizon; D05 | Weather lookup/service | WX-03..06 | P0 / exacthour/minutes/horizon/DST |
| POL-06 RECOMMENDATION | Midpoint ownership and mile-weighted means; D06 | Aggregation | MET-01..04 | P0 / conservation and hand-calculated examples |
| POL-07 RECOMMENDATION | Known No Travel blocking, deterministic ties, no all-blocked recommendation; D07 | Recommendation | RANK-04..08 | P0 / permutation, all-blocked, explanation facts |
| POL-08 RECOMMENDATION | UNKNOWN incomplete eligibility/staleness; D08 | Risk/aggregation/recommendation/UI | RISK-07; MET-03; RANK-07; UI-04 | P0 / no missing=Low and null average |
| POL-09 RECOMMENDATION | HGV, overlap tolerances and bounded fallback; D09 | Routing adapter/distinctness/service | ROUTE-01..07 | P0 / authentic alternatives, live gate, exact overlap |
| POL-10 RECOMMENDATION | Departure-relative snapshots, ETA distinction, risk categorical heatmap; D10 | Corridor/map/slider/details | HEAT-01..07 | P0 / unchanged ranking, meaningful 49 frames, duplicateLow |
| POL-11 RECOMMENDATION | Free-only/no-required-card access, limits/licenses/attribution; D11..13,D17..18 | Adapters/UI/deployment/docs | MAP-05; DEPLOY-05..06 | P0 / official terms and later actual account gate |
| POL-12 RECOMMENDATION | Backend domain authority, strictTS/DRF, one typed client; D14..16 | Domain/adapters/views/types/client | API-01..06; RISK/MET/RANK; futurelint/types | P1 / code boundary inspection + actual checks |
| POL-13 RECOMMENDATION | Input/time/load bounds; D20 | Form/API serializers | API-02..04; UI-01 | P1 / frozen clock/DST/invalid inputs |
| POL-14 RECOMMENDATION | Bounded batches/retry/cache/quota/error shape; D21 | Provider transport/service/API | WX-06..09; WX-11; API-06..09; ROUTE-06 | P1 / recorded failure responses and request counts |
| POL-15 RECOMMENDATION | Accessible synchronized professional UX; D22 | Form/cards/map/legend/state panels | UI-01..05; MAP-02..05; HEAT-07 | P1 / component + keyboard/mobile screenshot checks |
| POL-16 RECOMMENDATION | Envsecrets, production CORS/HTTPS, health/wakeup; D23 | Config/deploy/APIclient/loading | DEPLOY-01..03; API-06; UI-03 | P0 / actual hosted requests/config review |
| POL-17 RECOMMENDATION | Zero scrub requests, persistent map, lazy chunk, measurable budgets; D10,D23 | Map/slider/Vite output | HEAT-02; PERF-01..03; MAP-04 | P1 / network/frame/profile/build evidence |
| POL-18 RECOMMENDATION | Dependency/license inventory and minimal additions; D19 | Manifests/locks/docs/dependencies.md; future README content | DEL-01; PERF-02 | P1 / actual dependency audit/license/build report |
| POL-19 RECOMMENDATION | Deterministic fixtures and separate live smoke; D16 | Backend/frontend tests and e2e config; future trip fixtures | ROUTE-07; WX-10; E2E-01..03 | P0 / offline enforcement and honestlive status |
| POL-20 RECOMMENDATION | Optional compact CI/generated OpenAPI | Future workflow/schema tooling | DEL-04 | P2 / only if it fits fixedtime box, actualgreenchecks |
| POL-21 RECOMMENDATION | Explicit play/pause, never autoplay/reduced motion; D10 | Heatmap feature/native controls | HEAT-08; HEAT-02; PERF-04 | P2 / timer lifecycle, accessible explicit action, zero request count |
| POL-22 RECOMMENDATION | Estimated truck marker from existing checkpoint ETAs; D10 | Backend corridor/checkpoints; map display | HEAT-09; CP-04; PERF-04 | P2 / geometry/time fixtures, clamp and selected-route display |
| POL-23 RECOMMENDATION | Combined/wind/rain/snow codes only within500 KB payload; D10,D23 | Corridor serializer/map filters | HEAT-10; PERF-02..04 | P2 / measured compressed size, conditional capability/control |
| POL-24 RECOMMENDATION | 10 analyses/10min/IP and30 geocode/min/IP plus global guard; CHANGED D21 | API throttles/service | API-08..09 | P1 / frozen-clock windows and shared guard |
| POL-25 RECOMMENDATION | First300-coordinate weather quota measurement; >100 requires lower-cap proposal before API orchestration; D21 | Feasibility spike/plan/provider accounting | WX-11; API-08 | P0 / observed units/parameters, hold on missing or high-cost evidence |
| POL-26 RECOMMENDATION | System/manual light-dark CSS-variable theme/refined type; CHANGED D22 | Plain CSS/theme controls | UI-05..06; PERF-02 | P2 / contrast/focus/system/manual behavior, measured optional font size |
| POL-27 RECOMMENDATION | Transform/opacity DOM motion, reduced motion, no layout shift/library; D22 | Map/results CSS/Web Animations | UI-07; PERF-04; MAP-04 | P2 / actual visual/cleanup/layout evidence and disabled-motion case |
| POL-28 RECOMMENDATION | Selected-distance risk strip/SVG from midpoint-owned segments; D22 | Backend risk_profile/API; selected-route SVG | UI-08; MET-01..04 | P2 / distance partition equals backend, no chart library |
| POL-29 RECOMMENDATION | Default-live/config-disableable deterministic simulation, identity/banner/cache isolation, all six presets and real engine; APPROVED D24 | scenario_weather adapter/service/schema; trip/results labels | SIM-01..10; E2E-04; DEPLOY-06 | P1 / real adapter/domain/API/browser, intended risk/comparison branches and flags |
| POL-30 RECOMMENDATION | TomTom gate fails -> STOP before switching; ORS alternatives100 km; user owns key/accounts; D09,D11,D17,D18 | Plan/adapters/env/deployment docs | ROUTE-07; DEPLOY-05..06 | P0 / actual eligibility/truck/timing evidence, no plaintext key in chat |

## Planning constraints and completion limits

- RECOMMENDATION | User constraints:16 working hours/4 calendar days including planning. The user reports elapsed time; never invent actual hours, start/deadline or remaining balance. Gates: API7h, local journey10.5h, hosted13.75h. Additions are time-boxed inside M7-M9/reserve; the total remains16.00h.
- RECOMMENDATION | Planning is closed with all24 decisions recorded and AGENTS.md/five docs reconciled. This approval task completes documentation only; next phase is implementation, one focused user-issued task at a time. It does not mean any PDF feature is implemented. All implementation/evidence rows remain **PLANNED / UNEXECUTED**; approved policy is not a passed acceptance test.
- RECOMMENDATION | A request returning fewer than three routes or insufficient forecast coverage is handled honestly but is not used to claim full requirement compliance. A successful complete assessment demonstration must show three genuine distinct routes and a working map/forecast journey on the hosted app.
- UNVERIFIED | No application, fixtures, test results, build output, deployed URL, GitHub repository or Loom exists in the inspected workspace. External accounts or previous work elsewhere were not inspected; this is not a claim they do not exist outside the workspace.

## Authorized foundation task mapping

| Task goal | Existing path(s) | Acceptance/evidence |
|---|---|---|
| Git/local commit, ignore PDF/secrets/artifacts | .gitignore, .gitattributes, tools/check_staged.py | FND-08; staged review and final local commit report |
| Backend packages/config/production failure | backend/config, apps/routing, domain, providers, tests | FND-03..04; no feature logic |
| Frontend strict shell/API URL/live health | frontend/src/App.tsx, api/health.ts, .env.example | FND-05; component tests/live browser |
| Health liveness/readiness | backend/apps/routing/views.py | FND-02; provider/DB-independent |
| Test/lint/types/build pipeline | backend/pyproject.toml, frontend configs/manifests | FND-06 |
| Local environments/examples/entry point | dev.py, backend/.env.example, frontend/.env.example | FND-01..03 |
| Linux CI syntax and exact case/spaced path | .github/workflows/ci.yml, tools/check_ci.mjs | FND-07; execution remains UNVERIFIED |
| Dependency locks/licenses/sizes/audits | requirements.lock, package-lock.json, docs/dependencies.md, tools/audit_python.py | FND-09 |
| README headings and real command guidance | README.md, AGENTS.md section10, docs/foundation.md | FND-01..09; README content deferred |
