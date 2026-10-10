# RouteShield approved delivery plan

RECOMMENDATION | Planning closed2026-10-10; current contract18 APPROVED/6 CHANGED architecture decisions and three OPEN RELEASE GATES owned by user. Foundation, risk, geometry/checkpoints, aggregation and ranking are committed/tested; spike evidence is recorded. Provider adapters/trip API/UI/hosting remain planned. This documentation task starts no development; user-reported elapsed time only.

## Evidence and scope

- REQUIREMENT | Canonical source: `Requirements/fs-assessment-spotter.pdf`, pages1-2, fully read and visually inspected in Phase0. React and Django are the only mandated technologies.
- REQUIREMENT | PDF inputs: origin/destination/departure/load; three API routes; weather at10/25/50-mile checkpoints using arrival time; printed hazard/load rules and ordered recommendation; map with routes/checkpoints/risks/ETAs/summaries; corridor heatmap and0-48h slider.
- REQUIREMENT | Deliver GitHub repository, hosted app and5-10min Loom. Printed weights40/35/10/5 total90%; no missing10% category is invented.
- RECOMMENDATION | User constraints:4 calendar days/16 working hours including planning. **The user reports elapsed time**; no actual hours, remaining balance, start date or deadline is inferred from these allocations.
- RECOMMENDATION | Working name RouteShield. All PDF references retain exact Requirements/fs-assessment-spotter.pdf case for Linux.
- RECOMMENDATION | Free tier only, no plan requiring a card. If provider/host requires payment/card, STOP and tell the user. User creates TomTom key and Cloudflare/Render accounts later; never request plaintext keys in chat, use local .env/host dashboards.
- UNVERIFIED | Phase0 inventory before docs were created contained AGENTS.md and the PDF, no application/config/manifests/fixtures. This approval task reconciles the five existing planning docs and AGENTS.md; no scaffold or executable tests existed at approval; see the subsequent foundation record below.
- RECOMMENDATION | Phase0 PDF extraction emitted cross-reference warnings; independent in-memory PDFium inspection confirmed both complete pages. The source PDF remains unchanged.

## Historical Phase0 AGENTS.md audit and diff summary

RECOMMENDATION | The earlier audit is now applied, adjusted for the user's decisions. Keep the small-task discipline, backend-only domain rules and truthful verification. This table summarizes every changed AGENTS.md section; source text is the root AGENTS.md.

| Section | Before -> approved documentation change |
|---|---|
| Header | Earlier working title/rename note -> RouteShield, dated approval2026-10-10. |
| 0: working rules |16h only ->4 calendar days/16h including planning, elapsed from user; undocumented defaults -> approved frozen contract and OPEN/stop rule; planning closed, next phase one focused user-issued implementation task. |
| 1: mission | Printed weights -> explicit90% total/no invented10%; React/Django alone mandated, other technologies approved choices. |
| 2: authority | PDF reference -> canonical Requirements/fs-assessment-spotter.pdf; dated APPROVED/CHANGED contract precedes this file; proposed/open entries never authorize work, unverified facts remain evidence gates. |
| 3 title/3.1 | Authoritative-summary framing -> PDF transcription plus approved conventions; printed risk table/operators retained, ordinal meaning distinguished from PDF. |
| 3.2 | Defaults -> binding continuous bands/strict loads/no rounding; individual/hazard/adjusted/final risk retained; sustained wind; UNKNOWN floor, known blocking, null average/ineligible incomplete routes. |
| 3.3 | Per-route/default spacing -> common10/25/50 interval by longest route, cap warning/failure; calibrated chainage/provider timing, no guessed uniform speed; UTC/IANA/DST validation; midpoint disjoint ownership/nullable full average. |
| 3.4 | Warning on an all-blocked recommendation -> recommended_route_id=null and separate complete least-blocked diagnostic; canonical-ID ties/real explanations; mixed unknown/blocked distinction. |
| 3.5 | Rain-only/nearest-hour -> rain+showers, snow depth not water equivalent, validated conversions/hourly rates; enclosing(t-1h,t] row; horizon through latest ETA or departure+48, explicit unavailable data. |
| 3.6 | Generic provider/overlap -> TomTom truck/cumulative timing gate, STOP before provider switch, ORS100km conditional cap; length-weighted symmetric overlap/100m/0.5mi/>90%; <=2 genuine waypoint calls and honest partial-route limits; cargo not gross vehicle weight. |
| 3.7 | Generic heatmap -> all-route pooled corridor,49 departure-relative frames, one browser response/bounded upstream batches, constant-hue categories/known evidence; explicit playback, Python ETA-derived marker and size-gated hazard filter, no HTTP/reranking. |
| 4: boundaries/stack | Alternative tool names/default hosts -> approved HTTPX/dataclasses/DRF/strictTS/Vite/TanStack/MapLibre/OpenFreeMap, test/lint/type tools, Cloudflare/Render/Gunicorn/WhiteNoise; frontend position/ETA logic forbidden. |
| 4: layout | PDF in docs -> Requirements/fs-assessment-spotter.pdf; plan.md added; scenario_weather provider, recorded fixtures, profile/source-label display paths; all paths marked future scaffold. |
| 4: API | Short summary -> full reconciled input timezone/optional scenario, all risk layers/nullable IDs, profiles/49 frames/truck positions/conditional hazard codes/capability/source flags; health provider-independent; no interaction endpoint. |
| 5: reliability | Generic transport/cache/demo statement -> bounded coordinate/batch/concurrency/timeout/deadline work, terms-gated route/geocode caching and exact source-aware weather keys; six default-off/config-disableable scenario presets, real routing/real risk pipeline, immutable flag/banner/badge and no mixed cache/data; advisory copy. |
| 6: UX | Generic polish -> D22 P2 CSS-variable theme/refined type, optional size-gated font, transform/opacity DOM motion/existing-map easing/reduced motion/no layout shift, SVG profile; explicit missed-gate cuts and measured D23 size/frame targets. |
| 7: operations | Generic free-tier retry -> free/no-card STOP constraint, user-owned credentials/accounts/no chat keys; <=90s wakeup/user-triggered warmup, no keepalive pings. |
| 8: quality | dataclasses/Pydantic alternatives -> approved standard dataclasses, no added Pydantic layer. |
| 9: checks | Every change runs both app stacks -> layer-relevant actual checks, documentation checks for doc-only tasks; actual scenario adapter/browser fixtures and six labeled scenarios separated from live evidence. |
| 10: commands | Apparently executable POSIX setup/watch test -> TBD-until-scaffold PowerShell explicit venv paths and Linux paths, matched pytest/Ruff/mypy/Vitest/ESLint/tsc/Playwright, non-watch tests; Linux-only Gunicorn; no setup during doc task. |
| 11: security | Generic throttling ->10 analyses/10min/IP,30 geocode/min/IP/global guard, best-effort caveat, measured300-coordinate weather gate and >100 lower-cap proposal before orchestration. |
| 12: change management | Mandatory Git status -> only when Git authorized; a task prohibiting Git overrides it. No Git was run for this approval task. |
| 13: scope | Blanket extra-feature exclusion -> explicit approved D10/D22 refinements/D24 simulation within timeboxes; unrelated exclusions retained. |
| 14: budget | Original feature allocations -> M0-M11/reserve matching this plan, total16.00, three protected gates, additions inside M7-M9/reserve and exact P2 cut order; actual time/gate passes never invented. |
| 15: docs | Generic decisions/Loom -> frozen contract/dates/statuses/consistent five docs; persistently labeled severe/blocked simulation in Loom. |
| 16: done/report | Unconditional nonexistent app checks -> applicable document/reference/contract checks for doc-only work, explicit skipped app checks; standard changed/tested/failed-skipped/assumptions/incomplete report retained. |

## Sequenced time budget

RECOMMENDATION | Allocations are planned work, not elapsed time. Protected gates and all milestone totals are unchanged. The additions consume only existing M7-M9/reserve time. Tests accompany each implementation; M9 includes integrated evidence.

| Milestone | Hours | Cumulative | Exit evidence |
|---|---:|---:|---|
| M0: specification, research, architecture, approval |1.25|1.25| Dated approved contract/docs; actual elapsed only if reported by user |
| M1: minimal setup and production skeleton |0.50|1.75| React/Django health; locked justified deps/env examples; PowerShell/Linux commands verified |
| M2: pure risk, miles, aggregation, ranking |2.25|4.00| Exhaustive boundaries/ownership/eligibility/order/explanation tests |
| M3: routing, geometry, checkpoints, ETAs |1.50|5.50| Actual free truck alternatives and cumulative timing; distinct route sample; no unauthorized fallback |
| M4: weather normalization, batches, hourly frames |1.00|6.50| Synthetic unit/time/null fixtures, measured model coverage and accepted accounting/implemented quota guards ready before M5; user release grants remain open |
| M5: analysis/geocoding API orchestration |0.50|7.00| Validated/error/partial payload, quota/no-cache guards and TIME-03 integrated long-trip measurement; user chooses changes if35s cannot fit |
| M6: form and route comparison |1.50|8.50| Geocoded inputs, explanation/coverage/blocked/error states |
| M7: map/selection plus P2 theme/profile |1.00|9.50|0.80h core map/checkpoints/keyboard selection;0.10h theme;0.10h distance-risk strip |
| M8: cached heatmap/slider plus P2 playback/marker |1.00|10.50|0.80h categorical49-frame local slider;0.10h playback;0.10h ETA-derived marker; full local journey |
| M9: integration/defects/tests plus D24 simulation |2.00|12.50|0.50h scenario adapter/selector/source propagation;1.50h cross-layer/6-scenario browser/a11y/defect verification |
| M10: deployment and hosted verification |1.25|13.75| Actual production frontend/backend/three-route/map/slider journey |
| M11: README/submission/Loom |1.50|15.25| Accessible repo/live URL/screenshots, actual5-10min recording with labeled simulation |
| Reserve: defects and conditional P2 |0.75|16.00|0.45h defects;0.20h D22 motion;0.10h hazard filter OR optional font (not both) only if measured budgets hold |

- RECOMMENDATION | M7 allocations sum1.00; M8 sum1.00; M9 sum2.00; reserve sum0.75. D22 typography is part of theme/base CSS, SVG is a compact strip. Playback/marker reuse existing data; optional hazard codes are evaluated before serialization in M8's core, actual filter refinement uses conditional reserve. Only one of hazard filter/font receives0.10h. Unused P2 time returns to defects, never extends16h.
- RECOMMENDATION | Simulation interface/source metadata is part of the approved schema in M1-M5; its six concrete presets/selector and verification are funded in M9. No new service/library/ranking shortcut. The7h and10.5h gates are the live assessment journey; simulation must be finished and labeled before the hosted13.75h gate/recording.
- RECOMMENDATION | Four relative days: Day1 M0-M2(4h); Day2 M3-M5 + first1h M6(4h); Day3 remaining M6, M7-M8 + first1.5h M9(4h); Day4 remaining M9, M10-M11/reserve(4h). No calendar deadline is inferred.
- RECOMMENDATION | Protected domain/integration work receives5.25h plus feature tests; UI/form/map/heatmap receives3.5h plus M9/reserve. Quality is continuous; missing assessment weight stays unassigned.
- RECOMMENDATION | Timeboxes are tight, not guarantees. If the user reports an allocation exceeded, use available reserve/released P2 time and report the impact; do not estimate elapsed independently.

## First feasibility spike and deployment strategy

1. RECOMMENDATION | Completed technical spike observed truck alternatives and sparse geometry-indexed cumulative timing. Production adapters validate this shape with synthetic fixtures; no additional technical access spike is required before non-display development. User owns unresolved plan/display/storage/attribution release answers and supplies credentials through local .env/dashboard; the agent never creates or requests plaintext keys in chat.
2. RECOMMENDATION | Completed spike:300 real coordinates/six requests and published calculator300 units; user accepted this accounting and approved200 pooled coordinates with variable/window/model-aware quota guard/default8000 daily stop. Actual charged counter remains unverified. Mandatory first/coarsen optional; >200 mandatory pooled points at50mi -> TRIP_TOO_LARGE. Implement QUOTA-01..03/BUDGET-01..02 before live orchestration quota use; no further300-cost measurement or100-cap approval is pending.
3. RECOMMENDATION | If TomTom has no free access, truck-mode alternatives or usable cumulative timing, **STOP and ask the user before switching**. ORS alternatives100km is not drop-in; no second integration preemptively. If native routes are too few, D09 permits <=2 actual deterministic waypoint calls within quota/deadline/detour limits.
4. RECOMMENDATION | Verify rain+showers/snow-depth/unit metadata/returned timestamps/horizon with a real sample; user confirms free-service eligibility as an OPEN RELEASE GATE. Non-display development with synthetic fixtures can continue, but release/reliance on an ineligible grant or a card/payment requirement stops; no paid plan or total-precipitation substitution.
5. RECOMMENDATION | Later authorized deployment: Cloudflare Pages + Render Free, no card-required plan, database/disk/background job/custom domain. Conditional Vercel/Koyeb require verified eligibility and no card; the user's account creation is a separate later step.
6. RECOMMENDATION | Use minimal health path after scaffold to expose runtime/CORS issues; no keepalive. Waking UI polls only during user action, bounded90s, cancellation; user-triggered pre-demo warmup allowed.
7. RECOMMENDATION | Hosted evidence: cold start, HTTPS/CORS/prod API URL, health/validation, actual live three-distinct-route trip, map/markers/slider, zero scrub requests, partial-data UI and persistent simulation identity on labeled presets. Simulation never substitutes for the live-provider/hosted gate.

## Risks, controls and gates

| Risk | Control/stop trigger |
|---|---|
| Alternatives/timing unavailable | Gate primary first, STOP for user choice after TomTom failure; honest1/2-route state is not full PDF compliance. |
| Quota excessive | Accepted published accounting;200 cap/variable-window-model guard/default8000 daily stop with DEMO_QUOTA_REACHED, process/restart caveat;10/10min/IP retained, no charged-counter/DoS guarantee. |
| Weather/time/unit mismatch | rain+showers, depth/hour, enclosing interval, horizon and metadata fixtures before map work. |
| UNKNOWN appears safe | Null complete average/ineligible incomplete routes, known block preserved; never missing=Low. |
| Density appears Severe | Constant-hue categorical layers, backend codes, exact point labels, duplicate-Low test. |
| Simulation mixes with live | Immutable true/preset versus false/null snapshot, separate caches, banner/badge on results/errors/stale, explicit re-analysis, same real engine. |
| Payload/motion exceeds budget | Measure full compressed fields/frame/network/JS sizes; hazard filter absent when over500KB, P2 cuts/reduced motion/no layout shift. |
| Free/card/license gate fails | STOP and report; no auto-upgrade, unverified access/terms never claimed passed. |
| Cold start/long routing exceeds deadline | Host waking UI stays bounded; routing<=25s within35s hard total/no timeout retry, explicit failures provisional; M5 integrated measurement asks user before envelope/deadline/payload change. |
| Time gate missed | Use the exact cut order below, preserve protected delivery/correctness and report incompletes. |

## Exact cuts at a missed time gate

RECOMMENDATION | At each user-reported missed **7h API**, **10.5h local journey** or **13.75h hosted journey** gate, stop starting/continuing unfinished P2 work and reclaim its remaining allocation in this order:

1. Optional self-hosted variable font (keep refined system stack).
2. Conditional hazard filter/per-frame extra codes (keep combined categorical frames).
3. Motion refinements: route reveal, stagger/count-up, eased camera, skeleton effects, decorative selection transitions (keep static accessible loading/focus/selection).
4. Distance-risk SVG/profile refinement (keep required checkpoint/mile summaries).
5. Manual theme toggle/dark-theme refinement (keep one accessible base theme/system typography).
6. Playback and truck-marker refinements (keep required native0-48 slider and ETA details).
7. If still behind, optional generated OpenAPI/CI refinement, gust fetching, extra browser targets and other unstarted optional tooling; never a preemptive second provider.

RECOMMENDATION | The same P2 order applies at all three gates; only work that remains can release time. At7h prioritize finishing the usable API before UI refinements; at10.5h prioritize the actual local map/slider journey then validation/deployment; at13.75h prioritize hosted verification and protected recording. Do not remove functioning required behavior merely to tidy scope. Report each cut/remaining requirement; if optional savings cannot restore delivery, ask for direction instead of silently dropping mandatory work or inventing more hours.

REQUIREMENT | Never cut risk/load boundaries, ETA weather, honest UNKNOWN/No Travel, actual alternatives, real map/heatmap/slider, hosted verification or Loom. D24 default-live/source identity/real-engine rules are required for any simulation; an unfinished scenario mode is reported, never exposed without labels or replaced by fake scores. Theme/motion/profile were previously blanket cuts: the user's CHANGED D22 now funds them as P2 within the timeboxes above.

## Small tasks the user can issue next

RECOMMENDATION | Each task starts with files/approach/acceptance IDs, then performs the authorized focused work and inspects applicable checks. This plan dispatches no task, install, Git operation, account action or deployment.

| Task | Focus | Acceptance gate |
|---|---|---|
| T01 (completed foundation) | Health scaffold/local pipelines/browser verified; Linux/hosting remain unverified | FND-01..09 |
| T02 (completed) | Pure hazard/load engine/dataclasses | RISK-01..08 |
| T03 (completed domain) | Ownership/metrics/checkpoints/eligibility/ranking/explanations; new200 default alignment pending | CP-01..06; MET-01..04; RANK-01..08; BUDGET-01..02 |
| T04 (spike completed, adapter pending) | Production TomTom sparse parser/distinctness/departAt/traffic/error normalization/no-cache policy | ROUTE-01..10; CP-01..06; ERROR-01..03; CACHE-01..02 |
| T05 | Weather normalization/model coverage/batches/weather-only cache/hour frames/conservative quota | WX-01..13; BUDGET-01..02; QUOTA-01..03 |
| T06 | Thin API/schema/guards/error/redaction and integrated long-trip latency gate | API-01..09; TIME-01..03; QUOTA-01..03; ERROR-01..03 |
| T07 | Form/cards/states/actual comparison reasons | UI-01..05 |
| T08 | Map/checkpoint selection/attribution after user display grant; reopen D13 first if prohibited | MAP-01..05; ATTR-01..03; UI-06; UI-08 |
| T09 | Cached categorical corridor/slider, timeboxed playback/marker and size-gated filter | HEAT-01..10; PERF-01..04 |
| T10 | D24 six presets/labels/config/source isolation and integrated deterministic browser/a11y defects, optional timeboxed motion | SIM-01..10; E2E-01..04; UI-07; PERF-01..04 |
| T11 | Authorized deployment/live hosted verification on user-created no-card accounts | DEPLOY-01..06 |
| T12 | README/dependency audit/repo/live links/Loom in authorized submission task | DEL-01..04 |

## Historical Phase0 documentation verification record

- RECOMMENDATION | Historical Phase0 inspected both PDF pages and official provider docs; it performed source/planning checks, no live-provider/account/app verification. That research is retained in decisions.md as dated evidence, not a current live pass.
- RECOMMENDATION | Approval document checks inspected:24 status/date/reason records (21 APPROVED/3 CHANGED/0 OPEN), frozen section31 lines,103 defined acceptance IDs with no missing references,16.00h with matching cumulatives and protected gates. PDF SHA-256 remains 567392cc666a1c19694e192982f85bb9578149f59f70377f0234ecde7f1850f1. Cross-document API/policy and complete AGENTS section diff reviewed; no elapsed time is inferred.
- HISTORICAL | At Phase0 those application/provider checks were future work; later foundation/domain/spike records supersede that inventory. Current gaps are provider/API/UI integration, user-owned release grants, actual charged counters, Linux/hosted execution and performance; this docs task uses local document checks only.

## Foundation implementation record (2026-10-10)

T01 foundation is implemented: Django/React health shell, environment guards, exact locked approved dependencies, minimal tests, lint/format/types/build, single-entry developer commands, local-browser screenshot and syntactically validated Linux CI. Details/evidence: [foundation.md](foundation.md), [dependencies.md](dependencies.md), FND-01..09.

AGENTS changes for this task: stack explicitly defers the map dependency; layout lists actual foundation files and distinguishes future features; health documents version/limited readiness; commands replace TBD templates with inspected Windows commands and corresponding Linux CI paths. No domain/provider/product policy changed. Linux CI/hosting execution and live provider feasibility gates remain UNVERIFIED. No elapsed working time is inferred; user has supplied none.

## Provider amendment implementation and measurement gates (2026-10-10)

- M3/M4 implement sparse progress, explicit UTC departAt/traffic=false/past-rejection-only exception, synthetic fixtures/no route-geocode server cache and safe JSON/XML/empty errors; weather model selected by measured non-null required-window coverage (WX-13), no assumed model.
- M4/M5 enforce200 pooled coordinates/50 per batch/two concurrent, mandatory first/coarsen optional/density warning/TRIP_TOO_LARGE and variable-window-model published accounting/default8000 daily best-effort restart-reset guard. Approx40 full200-unit analyses at app default vs50 at provider10000 before other usage; no charged-counter guarantee.
- **M5 explicit TIME-03 gate:** measure authorized integrated long-trip end-to-end latency (routing/body parsing/distinctness/pooling/weather/concurrent batches/serialization), record totals/call counts/payload/window/point count and environment; synthetic tests cannot clear a live-latency gate. Keep35s hard global deadline/routing read<=25s bounded by remaining time/no automatic routing-timeout retry. First/repeat spike52.149/14.749s are not controlled cold/warm/read-phase measurements.
- If long trips cannot fit, present **narrow supported envelope**, **raise deadline**, **reduce request payload** with measured consequences for the user's decision; keep current limits/explicit failures until that decision. Allocate this gate inside existing M5/M9/reserve; no added hours or invented elapsed time, total stays16.00.
- **Release/display gate:** RG-TOMTOM-DISPLAY, RG-TOMTOM-STORAGE and RG-OPENMETEO-ELIGIBILITY stay OPEN RELEASE GATE, owner=user; agents never mark resolved. Non-display development proceeds. User reports terms answers before live display/release; prohibited non-TomTom display reopens D13 before map work, no Copyright API call before display grant, no ORS switch without direction.

Current docs approval does not update committed300/12s code defaults. The affected files/tests and already-supported sparse/ranking behavior are listed in the acceptance document's implementation-impact inventory for the next user-issued task.

### AGENTS.md diff summary for these provider amendments

| Section | Every change made in this task |
|---|---|
| 0 | Current phase now records committed foundation/risk/geometry/checkpoints/aggregation/ranking and planned provider/API/UI work. |
| 2 | User-owned OPEN RELEASE GATES, agents never resolve them, non-display development permitted; prohibited cross-basemap display reopens D13 before map work. |
| 3.3 | Sparse geometry-indexed anchors/chainage interpolation and submitted-departure ETA reference replace one-anchor-per-vertex implication. |
| 3.5 | mp/h alias/array validity/actual values; defer weather model choice to measured non-null required-window coverage. |
| 3.6 | Sparse progress wording, explicit UTC departAt/traffic=false/no live traffic; past rejection exception only for routing time, retain ETAs; distinguish passed technical spike from open grants. |
| 3.7 |300 pending cap becomes200, mandatory-first/optional coarsening/density/TRIP_TOO_LARGE. |
| 4 current status/layout | Correct foundation-only/no-domain-logic sentence; explicitly flag pending300/12s code alignment; tests directory says synthetic. |
| 5 |200/50/two bounds;25s routing within35s/no timeout retry/M5 gate; variable-window-model/global8000 guard/reset/best-effort and40-vs50 math; conditional TomTom/on-map/near-weather attribution; no server route-geocode cache/persistence; synthetic-only/no real TomTom recordings; JSON/XML/empty normalization and key/URL redaction; weather cache key includes variables; scenario tests say synthetic. |
| 9 | Synthetic-only later offline fixtures/no committed real TomTom recordings; browser scenario tests say synthetic. |
| 11 | Replace stale first300/>100 pending gate with accepted accounting/200/8000 guards; charged-counter caveat; explicit key-bearing-URL/raw-error redaction. |

Other AGENTS.md sections, commands, numerical hazard/ranking policies and the16.00-hour budget were not changed.
