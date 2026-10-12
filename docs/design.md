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
