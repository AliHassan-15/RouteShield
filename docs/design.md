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
