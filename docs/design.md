# RouteShield interface foundation

Verified locally on Windows, 2026-10-11. Scope: reusable design system,
responsive shell, typed client and health startup states. Trip entry, results,
map, forecast controls and provider attribution remain later feature tasks.
No risk, ranking, forecast lookup, ETA or position rules were added to TypeScript.

## Art direction and tokens

Weather operations control room: warm paper, deep ink, restrained cobalt,
instrument ticks and terse readouts. The shell has a 48 px header, a 420 px
desktop console and a full-width mobile workspace. Small radii, hairlines and
asymmetric section layouts supply hierarchy; floating layers alone cast shadows.
The map is explicitly labeled as a development placeholder with no loaded data.

Source of truth: `frontend/src/styles/tokens.css`. Every theme has ten neutrals,
semantic canvas/surface/raised/inset/ink/muted/border aliases, 4 px spacing,
4/6/8 px radii, z-index layers, typography and motion tokens. Ticks appear on
numeric inputs, sliders, dividers and risk strips. Their gradients repeat a
one-pixel mark; no gradient fills are used as chrome surfaces.

| Token | Light | Dark |
|---|---|---|
| Canvas | #f6f3eb | #101c25 |
| Surface | #fffdf7 | #172730 |
| Raised | #fffdf7 | #22353f |
| Inset | #eeece3 | #0c171f |
| Ink | #182c38 | #f5f3e9 |
| Muted | #5b6b72 | #a5b8bc |
| Accent | #245fc0 | #8ab5f5 |
| Accent label | #ffffff | #101c25 |

Accent is reserved for interactive actions, selection and focus. Minimum
accent contrast across the four backgrounds: 5.11:1 light, 6.07:1 dark;
primary-button label contrast: 6.05:1 and 8.24:1. Muted text minimum: 4.68:1
and 6.17:1. Control-border minimum: 3.06:1 and 3.98:1. Hairline separators
are decorative boundaries, not the only indication of a control or state.

## Risk palette and measured checks

Labels, icon strokes and badge borders share each category's semantic color.
The following ratios are minimums over canvas, surface, raised and inset
backgrounds, so every risk label exceeds 4.5:1 and every shape/border exceeds
3:1. UNKNOWN is separate from the ordered levels and has a dashed treatment.

| Level | Shape | Light | Contrast | Dark | Contrast |
|---|---|---|---:|---|---:|
| LOW | Circle | #407554 | 4.56:1 | #dcffed | 11.87:1 |
| MODERATE | Diamond | #6b5115 | 6.31:1 | #f3dba0 | 9.37:1 |
| HIGH | Triangle | #693515 | 8.37:1 | #f3ba8f | 7.42:1 |
| SEVERE | Square | #5d2020 | 10.48:1 | #eca09c | 6.11:1 |
| NO_TRAVEL | Crossed octagon | #401722 | 13.01:1 | #df889b | 4.93:1 |
| UNKNOWN | Dashed ring | #596970 | 4.82:1 | #a5b8bc | 6.17:1 |

Dependency-free check: from the root, PowerShell
`node "./scripts/design/check.mjs"`; Linux uses the same command. It reads the
actual CSS tokens, linearizes sRGB for WCAG contrast and applies the Machado
2009 full-deficiency matrices in linear RGB. Simulated colors are measured in
OKLab. Below, each cell is **100 × Euclidean OKLab difference / 100 × lightness
drop**, LOW toward NO_TRAVEL. An engineering guard requires difference >=5
and lightness drop >=2; these are regression floors, not a medical or universal
perception guarantee. Shape and visible text remain essential.

| Theme | Adjacent levels | Protanopia | Deuteranopia | Tritanopia |
|---|---|---:|---:|---:|
| Light | LOW / MODERATE | 11.13 / 10.24 | 8.08 / 5.92 | 13.96 / 6.10 |
| Light | MODERATE / HIGH | 8.25 / 7.90 | 6.05 / 5.92 | 7.40 / 6.00 |
| Light | HIGH / SEVERE | 7.24 / 6.11 | 6.07 / 5.40 | 5.52 / 5.40 |
| Light | SEVERE / NO_TRAVEL | 5.77 / 5.09 | 7.52 / 6.87 | 7.62 / 6.68 |
| Dark | LOW / MODERATE | 11.75 / 9.97 | 9.76 / 6.64 | 11.67 / 6.98 |
| Dark | MODERATE / HIGH | 8.41 / 8.32 | 6.54 / 6.53 | 8.20 / 6.96 |
| Dark | HIGH / SEVERE | 7.64 / 6.09 | 6.39 / 5.28 | 5.46 / 4.75 |
| Dark | SEVERE / NO_TRAVEL | 6.84 / 6.22 | 6.10 / 5.68 | 5.80 / 5.64 |

Executed result: no failures; minimum difference 5.46, minimum lightness drop
4.75. An initial palette failed these guards and was revised before completion.
The unit test mutates LOW to white and verifies that the contrast guard fails.
The dev guide's displayed measurements are checked against script output.

## Typography and theme startup

Instrument Sans supplies compact, readable labels with restrained variable
weights; JetBrains Mono supplies distinct numeral shapes and tabular readouts.
Both are self-hosted normal Latin variable WOFF2, package version 5.3.0,
OFL-1.1; complete licenses ship in `frontend/public/fonts/`. Exact dependency
and installed sizes are recorded in `docs/dependencies.md`.

| File | Shipped bytes |
|---|---:|
| Instrument Sans Latin normal | 30,092 |
| JetBrains Mono Latin normal | 40,404 |
| Total | **70,496**, below 90,000 |

Sans alone is preloaded. Both faces use font-display swap. Fallback metrics
were measured with Canvas TextMetrics in the real Chrome session at 100 px,
using `RouteShield Departure Load 0123456789`:

| Face | Width | Font ascent | Font descent |
|---|---:|---:|---:|
| Instrument Sans | 1881.400 | 97 | 25 |
| Arial | 1851.465 | 91 | 21 |
| JetBrains Mono | 2220.000 | 102 | 30 |
| Courier New | 2220.361 | 83 | 30 |

Instrument Fallback: size-adjust 101.617%, ascent 95.456%, descent 24.602%,
line gap 0%. Mono Fallback: size-adjust 100%, ascent 102%, descent 30%, line gap
0%. These align measured width/line metrics where Arial/Courier are available;
they cannot guarantee matching every glyph or fallback OS. The local desktop
browser capture's buffered layout-shift observer recorded no shifts (CLS 0).
Slow-network font-swap behavior on other hardware remains unmeasured.

Scale: 11 px micro label, 13 px supporting/control text, 15 px body, 20 px title,
28 px heading and 40 px numeric metric. Data uses tabular numerals; headings
use moderate weights, not an all-bold hierarchy.

System/light/dark preference is stored defensively. `public/theme-init.js` is
an external blocking script before the application module; it resolves theme
before first paint without inline JavaScript. Storage denial falls back to
system preference. System changes update the current theme while system is
selected. View Transitions supplies a progressive crossfade; unsupported
browsers change theme immediately. No provider environment variable is exposed:
Vite embeds only the documented public `VITE_API_BASE_URL`.

## Primitives, accessibility and motion

- Native buttons, inputs, select and range retain browser keyboard behavior
  with custom appearance. Labels/hints/errors are linked, numeric units remain
  visible, controls use 44 px touch targets and a 2 px focus-visible outline.
- Segmented choices use a roving radio group; tabs use linked tab/panel ARIA,
  automatic activation, wrapping arrows and Home/End. The indicator translates.
- Popovers use the native API with viewport-clamped positioning, focus entry,
  Escape/light dismissal and focus return; the fallback preserves these paths.
  Tooltips open on hover/focus and dismiss with Escape. Toasts announce through
  a live region and have a keyboard-accessible dismissal action.
- Cards/panels, badges, skeletons, empty/error states, tick dividers, metric
  tiles and proportional risk strips are presentation primitives. The risk
  strip only proportions supplied category miles; it classifies nothing.
- The original shield/route logo and 33 custom inline SVG icons need no icon
  package. Risk shapes also work without color; forced-color styling preserves
  boundaries and selection indicators.
- Mobile sheets have peek/half/full snaps, pointer capture and cancellation,
  a focusable handle with arrows/Home/End/Escape, and inert collapsed content.
  Escape from content returns focus to the handle. The skip link reveals and
  focuses the console after inert is removed. A clipped sheet dock keeps the
  persistent advisory visible at every snap; console content scrolls separately.
- Motion lives in `lib/motion.ts` and `styles/motion.css`: 120/200/240 ms actions
  and 480 ms shell entry; named fade/entry/exit/shimmer/busy transitions animate
  transform/opacity only. CSS linear() provides a spring-like easing with a
  cubic-bezier fallback. Reduced motion removes movement, including shimmer
  and theme crossfade, while keeping every state available.

The persistent strip and advisory popover use this exact D22 copy:
“Weather-based planning aid. Forecasts and truck restrictions may be incomplete;
verify conditions and road restrictions before travel.” No attribution is
invented while basemap/provider data is absent.

## API and unavailable states

The shared `api/types.ts` remains the contract. `api/client.ts` supplies the
public base URL, AbortSignal propagation, bounded client waits, basic success
shape guards, typed ApiError, safe request ID and numeric Retry-After support.
Every one of the 18 public codes in docs/api.md has fixed professional recovery
copy and an action. Arbitrary upstream exception/message text is not displayed.
The health shell never submits an analysis or geocode request.

TanStack Query 5.104.1 was already installed; no fetching dependency was added.
Analysis defaults have no automatic retry, focus refetch or reconnect refetch.
Only health retries transient failures: at most seven total attempts, each
bounded to five seconds and the remaining shared 90-second wake window, with
5/10/15-second bounded backoff. Pending requests are cancelled at the window
limit. A healthy result stops automatic fetching. Unreachable offers an
explicit retry which starts a new window; no keepalive or provider call occurs.
Checking/waking/healthy/unreachable are accessible statuses. A global branded
error boundary offers reload and does not render the thrown diagnostic.

## Style guide and verification

With dev servers running, `/style-guide` is the lazy living reference, with
synthetic specimens clearly labeled. The compile-time DEV branch removes its
import from production. `frontend/scripts/verify-build.mjs`, called by the
existing build command, checks emitted JS/CSS for guide markers/styles/example
copy, enforces JS/font budgets, validates the single font preload and checks
blocking theme-script order. It does not change any backend limit.

Final checks executed and output inspected:

| Check | Result |
|---|---|
| Frontend lint | Passed, zero warnings |
| Strict TypeScript | Passed |
| Vitest | 42 passed, five files |
| Production build / emitted-artifact checks | Passed |
| Initial JS | 275,168 raw bytes; **85,140 gzip bytes** (Node gzipSync default); Vite printed 86.03 kB gzip; both below 200,000 |
| Fonts | Exactly two WOFF2 files; 70,496 bytes |
| Guide in production JS/CSS | Absent; primary preload exists; theme bootstrap first |
| Contrast / three CVD simulations | Passed; tables above |
| Real Chromium tests | Four passed: three design checks plus live-health smoke |
| Backend regression suite | 1,566 passed; two optional live-provider smokes skipped |
| npm registry advisory audit | Zero vulnerabilities |

Iterations used only changed-file tests. Initial browser locator failures and
a Windows text-encoding error were corrected. Browser checks exposed a mobile
focus race; focusing after removal of inert fixed it. Windows sandbox Vitest
worker-file errors were resolved by running the existing tests on the host.
Full frontend checks and the backend suite were each executed once at the end.
Backend lint/types/build were not repeated for this frontend-only task. No live
provider smoke, production hosting, map performance or trip journey was tested.

Real screenshots are git-ignored under `output/playwright/design/`, inspected
for alignment, clipping, contrast, responsive behavior and truthful states:

- `desktop-light.png`, `desktop-dark.png` (1440 × 1000).
- `mobile-light-peek.png`, `mobile-light-half.png`, `mobile-light-full.png`,
  `mobile-dark.png` (390 × 844).
- `style-guide-light.png`, `style-guide-dark.png` (full reference pages),
  `style-guide-risk-dark.png` (readable palette detail).
- `loading-skeletons.png`, `waking-up.png`, `error-fallback.png`.

Healthy screenshots use the real local API. Loading/waking captures delay only
local health in the browser; fallback is triggered by the guide's explicit
preview action. They are interface-state evidence, not hosted cold-start or
provider evidence. No remote requests other than npm registry traffic occurred;
application verification used localhost. Backend settings and the user's
existing backend/.env.example edit were preserved. AGENTS.md was not edited;
its build command remains valid and now includes the artifact guard. The color
check command above can be added to its Commands section in a later authorized
documentation task.

## Trip form

The Trip plan now extends the previous health-only shell: `frontend/src/features/trip/`
owns the form, selected-place comboboxes, browser-zone/DST validation, exact decimal
cargo tokens, display-only wind copy, spacing, cancellable analysis and local recents.
Versioned URLs restore valid future links once per history entry; storage retains
five places/trips and load/spacing preferences, with no persisted departure. The
typed `api/analysis-store.tsx` holds the backend response for the next results task.
Mobile submit uses progress peek; success opens half with a visible action bar.

Verified 2026-10-11: full frontend lint/types/78 Vitest tests/build passed once;
36 new unit tests and four new Chromium checks passed. Initial JS is **96,340 bytes
gzip** (Node default); fonts remain 70,496 bytes; no dependencies were added.
Nineteen inspected screenshots are in ignored `output/playwright/trip/`, including
320px mobile, DST/error/progress states and 200% reflow equivalent (640×480 CSS
pixels at 2× device scale; native browser zoom shortcuts were not tested).
One real Chicago–Detroit analysis, 45,000 lb/+3h, returned HTTP200, three routes,
RECOMMENDED in **8,658 ms**: routing1/geocoding0/weather3; no retries or response
recordings. Browser tests otherwise intercept synthetic API responses; the optional
live check requires `ROUTESHIELD_REAL_ANALYSIS=1`. Backend checks, hosting, map and
full results remain outside this task. The existing backend environment edit is preserved.

## Results experience

Added the dispatch ticket, server-ordered comparison table, radio route list,
ownership strips, coverage/notices, stale/simulation surfaces and shared recovery.
Trip/Results tabs preserve inputs and the prior analysis; selection-store exposes
selectedRouteId, selectedCheckpointIndex and hoveredRouteId to the next map task.
Formatting is display-only: bounded BigInt fractions/decimals, half-even rounding,
exact cargo, Intl destination time or explicit UTC. No risk/ranking/ETA calculations.
Ownership uses checkpoint.owned_miles; synthetic tests detect partition divergence.
Presentation fallback: Route 1..n from server rank/group order, with the same ID-token
substitution in otherwise unchanged API prose. Matrix ticks show published comparison
winners only. Original adaptive spacing is unavailable; notices show requested/effective
spacing. PROPOSED backend additions: human route labels, per-criterion winner facts,
and original effective spacing for an exact old/new interval notice. None implemented.
Verified2026-10-11: frontend lint and111 unit tests passed;33 new unit tests and4 new
Chromium checks. Initial compiler/build failures in test fixtures were corrected;
targeted33 tests and strict TypeScript/production build then passed. Initial JS gzip
103,639 bytes; fonts70,496 bytes; no dependency or backend changes. Browser checks use
synthetic interception except exactly2 live analyses at45,000lb/+3h: Chicago–Detroit
HTTP200/3 routes/RECOMMENDED/7,789ms; Santa Monica–LA City Hall HTTP200/3 routes/
RECOMMENDED/2,658ms; both recommend UI Route1. Combined routing2/geocoding0/weather4.
Twenty-nine inspected screenshots in ignored output/playwright/results/ cover all
statuses/criterion variants, themes, selection, notices, stale/simulation, skeleton/
timeout, mobile half/full,320px and200% reflow equivalent (640×480 CSS at2× scale),
plus both live heroes/matrices. The half sheet prioritizes the hero; full view exposes
freshness/IANA metadata. Native browser zoom shortcuts, backend suite, hosting and
map rendering were skipped; the map placeholder remains. No provider bodies saved.

## Map

Implemented 2026-10-12: the placeholder is replaced by one MapLibre instance behind
the vendor-neutral `features/map/contracts.ts` interface. React uses that interface,
an external selection-store subscription and a fake engine in tests. Engine/CSS/worker
load dynamically during idle after first paint; a tick-scale skeleton covers loading.
Three GeoJSON sources and 16 overlay layers update incrementally. Hover does not render
React or write source data. The layer interface and legend slot leave room for the
next heatmap/time-control task; neither those controls nor a checkpoint panel is built.

Display geometry uses API `[longitude, latitude]` coordinates. Each cumulative
checkpoint-owned mile range is divided by API total miles and mapped proportionally
onto the polyline's great-circle angular chainage. This preserves real bends/endpoints
despite small geometry/provider distance discrepancies; it does not calculate risk,
ownership, ranking or ETAs. Golden tests cover clipping, +/-1% provider distance and
degenerate geometry. Missing/invalid geometry skips route features and warns on the
card; invalid checkpoint coordinates skip markers and tooltips safely.

Selected traces are 6px with a 10px contrasting casing, API risk segments and extra
UNKNOWN/No Travel patterns. Other traces are neutral 3px with server-order solid,
long-dash and dot-dash identity; +/-7px offsets expose shared roads. Exact rendered
hits precede the forgiving hit box so an offset trace remains selectable. Label chips
use fractions .35/.50/.65, prioritize the selected route and try three vertical offsets.
They hide when they collide with another chip, critical symbols, endpoint labels,
controls, legend, footer or viewport bounds; cards remain the accessible alternative.

Runtime DPR-aware icons use existing tokens: circle/diamond/triangle/square/octagon/
dashed-ring, sized 12/14/17/19/22/19px. The calm symbol layer collides; High, Severe,
No Travel and UNKNOWN always allow overlap. Below zoom7 only indices divisible by4
survive for Low; every other level is retained. Closely spaced critical symbols can
still overlap geographically at low zoom; zooming and the ordered list expose them.

Verified official sources: [OpenFreeMap quick start](https://openfreemap.org/quick_start/)
and [OpenFreeMap home/attribution guidance](https://openfreemap.org/).
The quiet official Positron vector style is `https://tiles.openfreemap.org/styles/positron`;
its source is `https://tiles.openfreemap.org/planet`, glyphs are
`https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf`, and sprites are
`https://tiles.openfreemap.org/sprites/ofm_f384/ofm`. Dynamic tile URLs come from TileJSON.
Style, glyph, sprite and offline-background switch are public environment settings.
No account/key is required; no availability SLA is claimed. Basemap configuration,
transform and attribution handling all live in `basemap.ts`.
The loaded source attribution is rendered as its original text and official links:
`OpenFreeMap © OpenMapTiles Data from OpenStreetMap`. Official guidance requires
OpenMapTiles/OSM credit; the optional OpenFreeMap credit is retained too. Source HTML
is parsed into text/allowlisted HTTPS links, never injected. API TomTom credit retains
its unconfirmed flag; Open-Meteo credit retains the modification notice. A persistent,
expandable 320px-safe strip reserves its measured height above the mobile sheet.
TomTom non-TomTom-map display remains a user-owned OPEN release gate.

Both themes transform background/water/land/roads/labels into the existing ink palette;
fills/roads use .65 opacity. POIs, noisy label groups, raster layers and buildings/
extrusions are removed. Labels retain a 1.5px halo. Theme paint/image updates preserve
camera, selection and sources; the same idempotent overlay installer handles style
replacement/retry. The official style sometimes emits a nonfatal `boundary_3` numeric
filter warning at low zoom; this was observed during manual screenshots.
WCAG relative luminance measurements below use the worst background/land/water
swatch in each palette (conservative against the translucent fills), steady state:

| Theme | Labels | Low | Moderate | High | Severe | No Travel | UNKNOWN |
|---|---:|---:|---:|---:|---:|---:|---:|
| Light | 5.73 | 4.02 | 5.56 | 7.38 | 9.24 | 11.47 | 4.25 |
| Dark | 7.85 | 11.87 | 9.37 | 7.42 | 6.11 | 4.93 | 6.17 |

Neutral traces at .95 opacity measure 3.78/5.74 light/dark; the inactive hover state
was raised to .85 opacity for 3.20/4.92. Labels exceed4.5 and steady traces/markers3.
Fade-in frames are transitional, not a contrast-pass claim.

Keyboard: arrows pan, +/- zoom, Home/R recenter, brackets select checkpoints and
show the reusable tooltip, Escape dismisses it, Enter activates chips/endpoints.
Map focus reveals a hint; skip links before/after the region open/focus the mobile
console. Results has an ordered checkpoint disclosure with mile, ETA/zone, shape/risk,
weather or unavailable reason; focusing/selecting an item updates the map and map
selection scrolls/highlights the list. Polite live messages announce selection only.
Controls have 44px targets; fullscreen is feature-detected and restores focus.
Desktop padding includes the console; mobile padding follows measured sheet snaps.
Snap changes update padding without fitting; Recenter waits for the snap transition.
Manual pan/zoom suspends automatic fits until new analysis/Recenter. Fits use absolute
padding, maxZoom14 and minimum .005-degree bounds. Reduced motion jumps immediately.

MapLibre6.14.0's installed style specification has no `line-trim-offset`; draw-in uses
a supported line-gradient reveal, 700ms per trace/70ms stagger inside one900ms window,
with checkpoint/chip/segment opacity reveals. Selection pulses once. New analysis
interrupts a pending animation and skips the reveal rather than queueing it. DOM
motion uses opacity/transform; reduced motion disables all overlay animation.
No WebGL yields a designed unavailable surface; style/tile errors retain the overlay
on the offline background with a Retry toast. Cards/list remain usable, but this
fallback does not satisfy the PDF's full map requirement. Empty state centers the US.

Measured in Windows x64, Intel i7-11800H (16 logical processors), headless Chromium
156.0.8078.4 with software SwiftShader and precise memory/CDP forced-GC snapshots:
38,000-vertex first route plus two180-vertex routes prepared in20.7ms/applied in40.5ms
cold, and9.2ms/16.7ms after the tenth analysis. Preparation is memoized and idle-scheduled;
GeoJSON tolerance is .35. First900ms draw/camera window recorded eight50–181ms long
tasks, frame median83.35ms, p95/max200ms. The16.7ms smoothness target **did not pass**;
this is software-rendered evidence, not a native-GPU result.
After first→tenth analysis: JS heap23,337,396→29,136,472 bytes (+24.85%); DOM1224→1224;
listeners307→306; WebGL contexts1→1. Browser tolerances are +30nodes/+30listeners,
one context and heap<=1.5x baseline. Those bounds passed, but **no heap growth was
not proved**. Removing retained mutation results prevents keeping old analysis
payloads; remaining cache/JIT growth is a possibility, not a proven explanation.

Verification: full frontend lint and143 unit tests ran once. Initial strict compile
errors in test annotations were repaired; subsequent targeted checks passed, finally
64 affected tests (35 new map tests), changed-file lint, strict TypeScript and production
build. Four offline Chromium map checks passed, including canvas variance, overlap
selection, no console errors, theme/style replacement, mobile skip/credits and the
ten-analysis measurement. The later missing-geometry guard passed the64 affected
tests and manual screenshots; the full unit suite was not repeated. Tests never
fetch basemap/provider data. Production debug-hook absence is checked by the build.
Commands from `frontend/`: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`;
targeted Windows invocations use quoted Node executable/script paths and `vitest run`.
Final Node-default gzip: initial108,852 bytes; lazy engine286,023 plus worker144,614
=430,637 bytes. Existing fonts total70,496 bytes. Runtime npm audit found0 advisories.

Inspected screenshots in ignored `output/playwright/map/`: `empty`,
`desktop-light-six-shapes`, `desktop-dark-six-shapes`, `route-selection`,
`checkpoint-tooltip`, `overlapping-routes`, `declutter-low-zoom`, `declutter-high-zoom`,
`legend-expanded`, `fullscreen`, `mobile-peek`, `mobile-half`, `mobile-full`,
`mobile-credits`, `skeleton`, `webgl-unavailable`, `offline-render`,
and `real-santa-monica-la` (all `.png`). Real OpenFreeMap is used for manual synthetic
screenshots; the automated canvas check uses the offline background.
Visible fixes included host CSS height, double padding, camera cancellation, chip
clipping/critical-symbol overlap, shared-route hit targeting and expanded mobile credits.

Exactly two live example-chip analyses at45,000lb/+3h: Chicago–Detroit backend HTTP200,
31,922ms total; the manual response observer timed out at30s before seeing the body,
so route count/recommendation/browser wall time and its map screenshot are unverified.
Santa Monica–LA City Hall returned HTTP200/3routes/RECOMMENDED in6,169ms browser wall
(6,047ms backend), captured in dark theme. Observer timeout was corrected to40s;
no application limit changed. Combined real calls: TomTom routing2/geocoding0,
Open-Meteo4. No response recordings. The two-analysis cap prevents a Chicago retry
or repeating live screenshots after final visual fixes; both corridors in both themes
are therefore not verified. Earlier tasks' live results do not fill this evidence gap.
Backend tests, hosted/native-GPU/mobile-browser verification were skipped. No new
backend fields are required; the existing proposed human route-label field remains
optional and unimplemented. Heatmap, slider and checkpoint detail panel remain next-task work.

## Checkpoint inspector and risk profile

Implemented 2026-10-12 in `frontend/src/features/checkpoints/`: the inspector,
compact dock, SVG profile, reason templates, display geometry and typed synthetic
fixtures. Results adds session-remembered Compare/Profile/Checkpoints navigation
with a transform-only indicator and heading focus. Compare keeps the existing
recommendation/matrix/cards/details; Checkpoints exposes the ordered list. Profile
loads its chart and full inspector together in a lazy module. No dependency added.
Blocked/incomplete routes remain inspectable and explicitly labeled; map selection
does not force a sub-view switch. Responsive console remounts retain valid route
and checkpoint selection; genuinely new analyses reset to the server recommendation.

Selection includes hoveredCheckpointIndex. Hover updates only the chart interaction
subscriber and imperative map paint, leaving the React selection snapshot stable.
The map emits checkpoint hover and receives external hover through feature-state;
no hover source writes or provider requests occur. Leaving Profile clears its hover.
`focusPoint(lng,lat,options)` uses existing padded viewport bounds: visible points
do not move the camera; offscreen selections pan without changing zoom. Reduced
motion jumps. The real engine and fake implement the same interface. Keyboard
selection is announced once after400ms through the existing map live region.

The console dock sits outside the results scroller, reserves at least160px so the
half-sheet controls remain visible, and has previous/next, close and Details actions.
Expanded details scroll inside the dock. Profile always exposes the full inspector
under its chart. At short mobile/reflow heights, the full sheet reserves140px for
the map rather than232px, keeping the content scrollable. Controls retain44px targets
and the dock remains above the persistent advisory/safe area.

Inspector values come directly from Checkpoint/RiskResult/Weather/Trip/Metadata:
mile/total, four-place lat/lon with clipboard fallback, checkpoint-local ETA or
explicit UTC fallback plus UTC instant, actual forecast row timestamp, wind/rain/
snow units and individual hazard badges, optional display-only gust, cargo and the
four-step hazard/load-adjusted/final/load-evidence ladder. Every reason is rendered
by one template module; its completeness test reads both the generated API union
and the domain ReasonCode enum (eight codes). Templates restate measured values,
band level and threshold/operator supplied by the API; there is no threshold table,
classification or ranking in presentation code. Future codes remain visible as text.
All seven availability codes have distinct driver-facing explanations. Missing
values are n/a, UNKNOWN has no ordinal, known blocking evidence remains prominent,
and the API known risk floor is shown as “At least <level>”.

The profile reuses checkpoint-owned miles for its band; final risk shapes appear
above a neutral weather trace whose point shapes/colors use that hazard's API level.
Missing samples break the path; zero is retained. A zero precipitation message
requires every sample to be present and zero. Nice numeric axes add headroom with
no hazard threshold lines. Four ETA axis labels interpolate supplied checkpoint
UTC instants for display only and use supplied checkpoint zones/explicit UTC; they
never produce forecast sampling ETAs, weather rows or recommendations. Load markers
use explicit API escalation reason codes and changed wind layers. UNKNOWN/No Travel
markers remain visible. In dense plots (<24px/checkpoint), Low uses the map's same
index-divisible-by-four thinning rule; all other levels survive.

The chart is one slider control: Left/Right move hover by one, PageUp/PageDown by
five, Home/End reach endpoints, Enter/Space selects, Escape clears hover. Pointer
snaps to the nearest supplied mile; crosshair motion uses transform only. Global
brackets and dock steps clamp at endpoints; button/global-console edges give a
short reduced-motion-safe response. Selection updates map/list/dock/inspector and
the chart marker. A hidden series table and visible summary provide text equivalents.
Maximum known level and category totals are supplied aggregates; UNKNOWN mileage
uses the separate `summary.unknown_miles` field, not an assumed dictionary key.
Trace draw-in runs once per route opening using stroke-dashoffset; band/value fades
and selection pulses are bounded. Reduced motion removes all these effects.

Presentation fallbacks: Route1..n use the existing server-order labels; no new human
route-label field is invented. Forecast age is explicitly the conservative age at
the analysis snapshot from cache ages and fetched_at/generated_at, not a claimed
live feed. No new backend fields are required; the earlier human-label proposal
remains optional. Synthetic state fixtures are UI evidence, not provider/forecast-
lookup evidence; optional hazard boundary metadata is omitted from their excerpts.

Verification: the full frontend suite ran once:181 tests/12 files passed. Initial
full lint found three formatting issues and strict TypeScript found two invalid
Testing Library options; these were repaired. Subsequent changed-file lint passed,
96 affected map/Results/checkpoint tests passed, then the live-exposed UNKNOWN
aggregate regression passed in the final36-test checkpoint file (36 new unit tests).
Two offline Chromium checks passed, including no console errors/extra analysis,
keyboard/map/list/dock sync, preserved route/checkpoint after mobile remount, theme
and route switching, nonblank SVG, offscreen focus without zoom loss and visible
half-sheet controls. Final strict TypeScript/production build passed. Node default
gzip measured initial JS110,342 bytes (<200,000); lazy chart/inspector JS6,316 bytes;
lazy map/worker430,752 bytes. Existing fonts remain70,496 bytes. Production debug
hook absence passed. The map's raw chunk-size warning remains; no new performance
or memory claim replaces the earlier Map measurement.

Thirty inspected PNGs in ignored `output/playwright/checkpoints/`: profile light/
dark wind/rain/snow (six); inspector-high and inspector-load-no-travel (each with
a rules/footer capture); inspector-unknown-block/unblocked; unavailable-out_of_horizon,
missing_hour,missing_field,past_time,provider_failure,quota_exceeded,demo_quota_reached
(each prefixed `unavailable-`); dock-desktop/expanded/mobile-half; crosshair-hover;
chart-keyboard-focus; subnavigation-blocked; profile-320px; browser-narrow;
profile-reflow-200-percent; real-santa-monica-profile/inspector. Manual and automated
screenshots used the offline basemap under this task's localhost-only network scope.
The640×480 capture is a200% reflow equivalent with scrolling, not verified native
browser zoom. Visible fixes included default heading/definition margins, tall-
element capture clipping, dock controls, stale hover and responsive selection reset.

Exactly one live Santa Monica Pier→LA City Hall example-chip analysis at45,000lb/
about+3h returned HTTP200,3 routes,RECOMMENDED in5,325ms browser wall (4,047ms backend):
TomTom routing1/geocoding0, Open-Meteo1. No real response recording. An earlier40s
observer timeout sent zero analyses because port8000 returned404 for health; the
verified application was run on8001 with a process-only public frontend API URL.
No repository environment/provider setting changed and no unrelated server stopped.
The saved live Profile exposed “Unknown n/a mi”; the separate-aggregate correction
was verified synthetically after capture. Its screenshot predates that correction;
the one-analysis cap prevents a further live replay. Backend tests, fresh dependency
audit (no dependency/network allowance), hosted/native-GPU/other-browser/native-zoom
checks were skipped. Heatmap/forecast slider remain next-task work. User-owned
release gates remain OPEN; no elapsed working time was supplied or estimated.


## Heatmap and forecast slider

Implemented presentation of the existing D10 payload (2026-10-16). The decoder
validates the 49 frames, 0/1..5/9 level alphabet, intensity0..100, dominance0..4,
block/floor masks, coordinate ranges, mappings and nullable server truck positions.
The analysis snapshot retains the cached decode; slider state has a separate
external-store subscription and never changes the route-selection snapshot.
Worst-case200 points/49 frames/three routes with filters allocate **85,275 bytes**
in typed arrays (coordinates3,200; frame arrays78,400; trucks/masks3,675), excluding
the original response and JS object headers. Measured final hardware decode **3.20ms**;
this is below the8ms idle-scheduling threshold, so decoding stays synchronous.

Five independent heat layers draw Low→No Travel with fixed token hues and alpha
only. Weights use the server intensity/100 in its supplied category; no threshold,
classification or intensity formula exists in the frontend. Radius interpolates
linearly at zoom3/6/10/15 through28/48/64/84px. Opacity caps are.18 for Low and.48
for other levels. UNKNOWN has hatched gray points, Unavailable dashed hollow rings,
and known-block marks survive either. Exact sample shapes carry dominant W/R/S/L
glyphs and keyboard/hover details. Routes retain risk colors, thinner outlines and
contrasting casings above the field; checkpoint halos remain above routes.

One180ms rAF crossfade blends separate category weights and retargets from the
current display without queueing; writes faster than16ms are skipped. Reduced
motion selects the frame immediately. A400ms first field reveal follows the900ms
route reveal and is canceled by replacement. Sources/layers are reused through
hour/filter/selection and reinstalled through the existing theme/style path.
Explicit playback is1hour/1000ms at1x, with0.5/1/2/4x and Loop off initially.
Playback stops at the payload's last usable hour; Loop wraps only usable hours.
Manual pointer capture pauses; keyboard steps1/6h, Home/End and P are supported.
The track still permits unavailable hours and hatches them. UTC and local absolute
time preserve departure minutes and DST; arrival/snap uses supplied checkpoint ETA.
The arrival marker preserves the fractional ETA hour; only the jump action rounds
to a frame, with its exact ETA still visible.

Presentation-only associations: truck coordinates/miles come directly from the
server's **lat,lon,mile** tuples (point coordinates are **lon,lat**). Null after
arrival hides the marker and labels Arrived. During a glide only screen presentation
interpolates returned positions; it does not derive progress or ETAs. For the
current-cell readout, nearest great-circle sample is chosen within route mapping
candidates, or within the full point pool if mapping is absent. This is a sample
association, not forecast interpolation or off-road coverage. Hazard filters use
the supplied hazard codes with the existing combined intensity because the API
has no per-hazard intensity arrays; no new intensity is invented. Optional backend
proposal: provide per-hazard display intensities and an explicit truck→sample index
if exact attribution is desired. Neither is needed for this implementation.

Chromium156, Windows,16 logical processors, **Intel UHD Graphics / ANGLE D3D11**:
Vite dev/E2E mode with an offline basemap and preserveDrawingBuffer enabled:
feature-state through-render/idle median8.70ms/p9510.00ms (synchronous median.20ms);
preallocated GeoJSON setData median303.90ms/p95334.00ms (synchronous median.20ms).
The installed MapLibre6.14 style specification explicitly permits feature-state
in heatmap-weight; real browser drawing produced no expression errors. The faster
feature-state path is used. A worst-case full pointer scrub plus4x playback trace
measured final frame median4.20ms, p958.40ms, maximum21.00ms,1,423 frames; zero long
tasks>50ms and **zero browser request events, excluding none**. Trace artifacts
are ignored under output/playwright/heatmap. This is a measured local target pass,
not a guarantee on all hardware. Earlier repeats had p9512.60ms and16.70ms;
variability and the borderline earlier result are retained here explicitly. The single requested hardware attempt succeeded;
earlier functional checks also used software SwiftShader.


Retention evidence: ten consecutive worst-case analyses and **200 full playback
cycles** used one WebGL context. Between-step waits were accelerated while actual
rAF/rendering remained active and the4x setting/ordinary timer stayed enabled;
this is **not a ten-minute wall-clock soak**. Measured final loop window156,470ms.
After GC, DOM nodes1,427→1,435; listeners316→319; JS used heap22,948,360→26,912,708
bytes (+17.3%). These pass the recorded bounded-growth assertions, not proof of
zero retained allocation. The stress-run path benchmark also favored feature state
(11.00ms median vs304.60ms setData median); primary trace numbers above came from
an otherwise isolated offline-basemap measurement. The clean browser scrub test
also verified zero unrelated route-console React Profiler commits.

Verification: **224 frontend tests/13 files passed**, including **42 new heatmap
unit cases**. Full lint, strict type check and production build each ran once and
passed. After screenshot review, the corrected calm fixture, exact ETA marker, strict filter flag, readout badge/placement and manual helper
received scoped lint/type checks and the42-case heatmap rerun; the final CSS reflow, sample touch targets, opacity-only readout/legend motion
and label-priority changes received focused Vite asset rebuilds and bundle check.
Three new browser tests passed across clean scoped runs: zero-request keyboard/
pointer weights and exact h0 hash; calm/stormy canvas, theme/style preservation;
and ten replacements/200-cycle retention. Early runs exposed inadequate transition
waits, dev HMR measurement contamination and a rerun with the wrong basemap mode;
the corrected clean offline reruns passed without filtering request events.
Final Node gzip: initial JS**114,748 bytes** (<200,000), lazy heat controls**3,131**,
lazy checkpoint views6,462, lazy map/worker433,867. Heat-control CSS2.34KB gzip;
fonts remain70,496 bytes. Production E2E hook/guide exclusion passed; Vite's large
lazy-map chunk warning remains. No dependency or environment setting was added.

**33 PNGs inspected**, ignored under `output/playwright/heatmap/`: stormy-light/
dark-0/12/24/48 (8); calm-light/dark-24 (2); heat-on/off; samples-visible;
filter-combined/wind/rain/snow; route-closeup; truck-hour-4/16 and truck-arrived;
unavailable-hours-caption; legend-expanded; mobile-320-peek/half/full; slider-focus;
zoom-reflow-200; partial-availability; filter-omitted; heatmap-malformed;
real-santa-hour-0/24. Synthetic captures use the actual OpenFreeMap basemap.
Visual revisions: healthy-status badge no longer covers mobile time labels;
Options stays in the playback row; map padding/controls/legend reserve measured
control height; short reflow viewports scroll rather than hiding controls beneath
the sheet; route chips sit above the truck; readouts sit above the marker and include risk
shapes; sample buttons retain44px targets around12px dots; actual keyboard modality proves the
slider focus ring. Calm arrival evidence now agrees with its all-Low forecast.
Sparse high-zoom fields reflect supplied samples; density is disclosed rather than
inventing intermediate weather. Native Ctrl+zoom did not change Chromium's scale;
720×500 with vertical scrolling verifies reflow equivalence, **not native200% zoom**.

Exactly **one** live Santa Monica Pier→Los Angeles City Hall chip analysis at
45,000lb/about+3h returned HTTP200,3 routes,RECOMMENDED in**5,255ms** browser wall,
4,687ms service time: TomTom routing1/geocoding0, Open-Meteo1. The numeric send guard
is1; only numeric metrics and screenshots were saved, no real response recording.
Both heat hours rendered, but detailed basemap tiles had not appeared in the live
captures; live basemap completion remains unverified and the cap prevents a replay.
The real captures predate the final readout badge/placement, exact ETA-marker
placement and route-chip stacking adjustments. Synthetic
screenshots verify the loaded basemap and final stacking separately.

Backend tests, fresh dependency audit, hosted verification, other browsers and
native200% zoom were skipped/unverified within this frontend-only/network scope.
The200 cycles were accelerated, not a real-time ten-minute soak. No proposed
backend change was applied; existing user-owned release gates remain OPEN. The
pre-existing backend/.env.example edit is unrelated and excluded from this commit.
No elapsed working time was supplied or estimated.

Added frontend/src/features/heatmap/{decoder.ts,presentation.ts,overlay.ts,
HeatmapControls.tsx,heatmap.css,fixtures.ts,heatmap.test.tsx}, e2e/heatmap.spec.ts
and scripts/capture-heatmap.mjs. Integrated the analysis/selection stores, real/fake
MapEngine, workspace, App and inspector; extended the existing build-budget helper.
All backend, contract, decision and AGENTS files remain outside this change.

Synthetic fixture durations are20/21/22h with matching checkpoint ETAs and progress,
so intermediate truck hours can be inspected. They are explicit UI test data, not
real driving-time estimates or provider measurements.

## Motion, accessibility and performance audit

Measurements dated **2026-10-17 (Asia/Karachi)**; final documentation/browser verification completed **2026-10-22**. Frontend presentation only; no dependency,
backend, provider, risk, ranking, policy or limit changes. This section supersedes
older entrance timings above; earlier measurements remain historical evidence.

Motion inventory (source search: CSS animation/transition/keyframes, Web Animations,
rAF, map paint transitions, camera duration and scroll calls). `out` means
cubic-bezier(.2,.7,.25,1); `spring` uses the existing linear() token with its
cubic-bezier fallback. CSS reduced motion disables animations/transitions globally;
JS uses the same `motionOff()` guard. No animated interactive layout dimensions,
position offsets, margins or shadows were found. Fixed left/top positions are
placement, not animated properties. The two busy scans formerly looped; both now
settle after one entrance. Only explicit forecast Loop and skeleton shimmer repeat.

| Location / effect | Trigger | Duration / easing | Animated properties | Reduced motion |
|---|---|---|---|---|
| styles/motion.css: button, segmented/chip/heat press | Press/hover |120ms/out|transform, opacity|static|
| Button progress | Busy begins |200ms/out, once|transform, opacity|static|
| Tab indicator | Trip/Results |200ms/out|transform|instant|
| Sheet | Open/snap; drag follows pointer |240ms/spring; drag0|transform|instant|
| Toast | Enter/dismiss |200ms/out each|transform, opacity|instant; cleanup0|
| Skeleton | Loading |1800ms/ease-in-out, only CSS loop|transform|static, pseudo hidden|
| Header / console / legacy console children | Mount |200/480/240ms out; child delays0/60/100/140|opacity; console translate|static|
| View Transition root | Theme, supported browser |200ms/out|old/new snapshot opacity; group morph disabled|direct update|
| Tab panel / result sub-view / loading/error container | State/view change |200ms/out|opacity|instant|
| trip.css: sections, helper copy | Mount / load-rule display changes |200ms/out|opacity|static|
| Swap / floating label / input underline | Swap, resolve/focus |200/120/120ms out|transform|instant|
| Place dropdown / option highlight | Search open/close, active option |120ms/out|transform+opacity / opacity|instant; close cleanup0|
| Weight thumb / threshold tick / spacing indicator | Drag, weight/spacing change |120/out,200/spring,200/out|transform|instant|
| results.css: hero / risk strip | Fresh analysis |300ms/out|translate+opacity / scaleX|final state|
| Matrix rows / route cards | Fresh analysis |240ms/out; offsets below|transform, opacity|final state|
| Matrix/card selection outlines | Selection |200ms/out|pseudo opacity; focus outline never animated|instant|
| Stale banner / expanded warnings | Stale/expand |200/160ms out|transform, opacity|static|
| ResultsView CountMetric | Once per response identity |480ms, linear clock|fixed-width text only|final text; no count loop|
| map.css: initial tick field / tooltip | Map mount / checkpoint inspect |480/120ms ease-out|transform, opacity|static|
| Map checkpoint ring | Newly selected checkpoint |480ms ease-out, once|scale, opacity|not created/hidden|
| Map route draw / risk/checkpoint reveal / chips | Shared arrival |700ms per route,70ms stagger;160/200ms linear paint|line gradient/opacity, symbol opacity, Marker opacity API|final state|
| Existing map camera | Fit / focus / zoom |600ms cubic-out /300ms default /200ms default|existing camera only|duration0|
| Map line width / risk opacity | Selection/reveal |120/160ms map paint; global default0|paint properties|explicit0 on reduced setup|
| checkpoints.css: values / dock | Selection/open |180ms/out|opacity / transform+opacity|static|
| Profile trace / band / selection / crosshair | First reveal, select/hover |480/250/220/90ms out|stroke-dashoffset / opacity / scale+opacity / transform|instant|
| Checkpoint edge feedback | Bracket/step at an endpoint |160ms Web Animations|translateX|not created|
| heatmap.css: controls / hour / expanded legend | Analysis/hour/expand |200/120/120ms ease-out|transform+opacity / opacity / transform+opacity|static|
| Heat thumb feedback | Press/focus |120ms/out|opacity|instant|
| HeatOverlay frame / truck glide | Hour/filter changes |180ms linear, one retargetable rAF|separate weights; returned-coordinate presentation glide|instant|
| HeatOverlay first reveal | Shared arrival |300ms linear paint|heatmap opacity|final state|
| Renderer mouse/move/padding bootstrap rAF | Actual pointer/camera/resize/load |one scheduled frame; idle boot <=400ms|placement/coalescing, not a repeating animation|still schedules necessary I/O/render work|
| Focus and list scroll calls | Explicit keyboard selection/navigation |instant/auto; no smooth scroll requested|none|same|

`lib/arrival.ts` owns the named ARRIVAL timeline and MOTION token durations.
Nominal offsets: hero0-300ms; count0-480; matrix rows120/160/200/240 (280 when
No Travel adds a fifth row), each240ms; cards320/360/400, each240ms; routes100-800,
170-870,240-940; checkpoint/risk reveal940-1100; heat1100-1400; chips1440-1640;
end1800ms. The one-time staggered route draw is the documented >600ms exception.
Every element remains interactive; root pointer/key capture ends the timeline,
including all map/heat phases, before handling the interaction. Replacing an
unfinished analysis finishes both, with no queued entrance. Weak response identity
retains count progress across rerender, selection, tab, theme and sub-view remounts.
The fake clock and FakeEngine consume the same arrivalFrame function as MapLibre.
Actual compositor sampling times are retained in visual-audit.json; nominal
choreography is not a claim that a cold renderer meets the frame budget.

Fixes: separate650ms/950ms timers removed; count no longer restarts; camera fit
900->600ms; map arrival paint invalidation capped at60 updates/sec. MapLibre's
Marker.setOpacity replaces direct style opacity, which its own renderer overwrote
and exposed chips early. The vendor marker opacity transition is also disabled
for route chips: it otherwise eases from visible to hidden before the scheduled
reveal. The final compositor series confirms the corrected order, and the scoped
browser test asserts that no second CSS transition is applied. Heat styles now load before imperative marker DOM to
prevent an unstyled-card shift. Credit rows/slot, legend trigger and sub-view body
reserve space; the legend expands in its own scroll area. Sheet snaps keep type
metrics and height stable. Mobile full results reveal a500px console; at narrow,
tall viewports the page scrolls vertically instead of reducing mandatory form
fields to a few pixels. Short200% reflow retains its existing350px console.
Existing fixed-width metrics, opacity state/view fades, dock/tooltip/selection
motions and reduced-motion rules were retained. Copy ID visibly confirms Copied.

Layout evidence: the browser records both ordinary CLS and every raw shift,
including recent-input entries. Final normal-motion CLS and raw totals are **0 for all ten measured flows**. Earlier failures were real: arrival0.014315, sub-view0.056622,
legend0.039327 and sheet0.034989 raw. These drove the fixes, not exclusions from
the observer. The two scoped browser tests cover first load, arrival, Trip/Results,
Compare/Profile/Checkpoints, route and checkpoint selection, dock open/close,
legend, theme and320px sheet snaps; each asserts <=.01 even including recent input.

Reduced-motion selectors: .recommendation-ticket, .route-option,
.comparison-matrix tr, .tab-indicator, .results-view-indicator, .heat-control,
.heat-time, .heat-thumb, .button, .trip-section, .bottom-sheet, .inspector-dock,
.profile-trace, .profile-crosshair, .profile-selected, .map-selection-pulse and
.skeleton::after. Computed animation and transition durations were0s where present;
zero camera duration, settled metrics/heat, visible selection/focus and no playback
autostart passed. An explicit play/pause remains functional with instant frames.
One deterministic switch, VITE_MOTION_DISABLED=true, requires DEV and VITE_E2E=true;
it disables both CSS and JS motion. Unit tests exercise that switch and fake-clock
choreography. The same two browser tests were also run with the switch enabled.
Animation assertions await completion or use a fake clock; timed waits are for
measurement/capture windows, not racing assertions. Production verify-build rejects
MOTION_TEST_ONLY, VITE_MOTION_DISABLED and all Map/Heat/Console/Audit hook names.

Keyboard flow covers skip, origin/swap/destination, example selection, native date
and time subfields, cargo input/slider, spacing and submit, then results views,
route cards, matrix, map brackets, chart, inspector, heat hour/play, legend and
fullscreen. Escape previously got consumed by the map and trapped fullscreen;
it now exits and restores the control's focus. Route and checkpoint announcements
are polite/debounced400ms; hour announcements remain quiet during play/drag/key
repeat. Closed comboboxes no longer reference an absent list. Home, skip, credit
and request-ID targets were raised to44px. Custom DOM checks cover names, roles,
duplicate IDs, label/reference associations and44px targets (no accessibility
checker dependency was installed). Stable-state text contrast is measured from
computed foreground/background colors, skipping tiny tick-bar backgrounds that
sit outside their labels; it is not an antialiasing or screen-reader certification.
Final sweep: light minimum4.6804:1, dark5.9391:1; no name, role, duplicate-ID,
label/reference or touch-target findings. Risk strips have labeled legends,
profile uses shape markers, and heat/truck use shapes/text plus UNKNOWN hatching.
Native browser200% zoom remains unverified;720x500 is the documented reflow
equivalent. Theme startup's existing blocking script and fallback unit checks
remain; compositor theme frames show map continuity and the same selected route,
camera, hour12, wind filter and server truck position.

Performance evidence (Chromium156.0.8078.4; Windows;16 logical processors; real
OpenFreeMap; Vite DEV/E2E with preserveDrawingBuffer): **ANGLE (Intel, Intel(R) UHD
Graphics (0x00009A60) Direct3D11 vs_5_0 ps_5_0, D3D11)**, hardware rendering.
Worst fixture: three synthetic routes,200 pooled points,49 frames. Initial arrival
median8.4/p9533.2/max245.9ms;2 long tasks, max242ms,TBT272ms. One optimization pass
bounded repeated map paint writes; its remeasurement was median16.7/p95108.4/
max258.1ms;6 long tasks,max235ms,TBT410ms. Scrub plus full4x playback then measured
median4.2/p9516.6/max54.2ms,zero long tasks/TBT and zero request events. Reduced
arrival measured median8.3/p9541.7/max192ms;1 long task,max176ms,TBT126ms. The first
reduced comparison had a stale-snapshot race and was discarded; the helper now
waits for the exact new analysis identity. Traces include actual renderer work,
not only an rAF claim. Arrival smoothness/long-task targets remain MISSED; later
visual fixes receive one final verification trace without another optimization.
Final-source verification after the subsequent visual fixes (no second optimization):
arrival median8.4/p9537.6/max183.4ms,3 long tasks,max169ms,TBT207ms,CLS0;
scrub/full4x median4.2/p9512.5/max58.3ms,zero long tasks/TBT/requests,
CLS.0024165/raw.0045549; reduced arrival median4.3/p9550.1/max195.9ms,
1 long task,max169ms,TBT119ms,CLS0/raw.0000757. Decode1.5ms/85275 typed-array
bytes. These are the final reported numbers; arrival p95 and long tasks remain
above target. This trace precedes the final mobile CSS specificity and vendor
chip-transition corrections; their scoped browser/CLS checks were repeated,
with no additional performance optimization or claim. These measurements do not
establish production or hosted performance.

Final full frontend checks: lint, strict type check,245 tests/14 files and production
build passed. Added21 focused unit cases and two browser tests. An early focused
run failed before collection because the sandbox temporary directory disappeared;
using project-local TEMP/TMP fixed it. Browser localhost access required running
the owned server/runner outside the network sandbox, still with a hostname guard.
Initial browser assertions exposed the documented layout/keyboard defects; final
scoped runs passed. One additional project type check ran during initial integration;
the requested full lint/test/build and dedicated end-stage type check each ran once.
Build also invokes its existing tsc check. Final screenshot review exposed a mobile overflow specificity conflict and the vendor chip-transition flash. These CSS-only fixes passed the two scoped browser tests (final run20.9s),21 focused unit cases, scoped ESLint and a Vite-only asset rebuild plus production guard. A repeated focused run initially failed before collection when its deleted project TEMP directory fell back to protected Windows temp; recreating the project TEMP directory restored the passing run. The final browser width assertion permits the native vertical scrollbar gutter (305 content pixels in a320px viewport). Capture-helper updates received scoped ESLint checks. No backend suite, installs, dependency
audit, Linux/hosted check, other browser or assistive-technology session ran.

Production bytes (Node gzip level6): initial JS **115407** (106514 index +8893
shared presentation); lazy map engine289424, worker144614, checkpoint6467,
heat controls3130. CSS: initial12647, lazy map10468, checkpoint2004; fonts30092+
40404=70496 raw. Largest JS chunks: map, worker, initial index. Initial JS passes
200000-byte target. Profile and heat controls already remain lazy; moving heat CSS
into initial CSS is the intentional layout-stability tradeoff. No new dependency
or speculative library split was added. Vite still warns about the large lazy
map chunk; the warning is not suppressed.

Artifacts: output/playwright/motion-audit/ contains compositor frame series,
focus/320px/reflow/reduced/error screenshots, the Playwright WebM, raw Chromium
trace, CLS/DOM/performance numeric reports and a persistent one-send live guard.
Synthetic data stays visibly synthetic in capture content; no real response is
saved or committed. All screenshots are inspected before commit. The single
Santa Monica Pier -> Los Angeles City Hall live analysis uses45000lb/+3h; the
capture gate requires MapLibre idle after arrival plus loaded tiles, in each theme.
Live evidence from the2026-10-17 measurement session: **HTTP200,3 routes,RECOMMENDED,3540ms browser wall /2984ms service**; TomTom routing1, geocoding0, Open-Meteo1. Both light/dark hour0 captures passed post-arrival idle and loaded-tiles checks. The persistent guard records exactly one send; no live retry occurred. Final evidence contains33 synthetic PNGs plus two real PNGs, all visually inspected in the final contact sheets on2026-10-22. The refreshed Playwright video is output/playwright/motion-audit/arrival-audit.webm, **25.32s**,1440x1000/25fps/VP9 (duration read from the installed Playwright FFmpeg metadata). Compositor samples nearest0/150/300/600/1000/1800ms were desktop13.31/146.49/284.00/600.68/979.77/1792.26ms and mobile-0.92/149.08/303.22/603.26/994.89/1794.93ms; negative0 denotes the last pre-arrival frame. Theme samples were-6.35/51.96/77.00/206.22/356.18ms. Frame selection uses compositor timestamps rather than serial screenshot sleeps.
