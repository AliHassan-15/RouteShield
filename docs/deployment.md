# Local deployment preparation — Render Free + Cloudflare Pages

This is a local preparation record, not a deployment. No account, remote, push,
live provider request or hosted verification was performed. The only external
requests authorized for this task are OpenFreeMap browser assets for the CSP
check. Account eligibility and current dashboard behavior remain UNVERIFIED.
Follow the three user-owned release gates in [decisions.md](decisions.md) before
publishing provider results. Stop if either host requires a card or paid plan.

## Runtime and configuration

The JSON-formatted `render.yaml` is valid YAML and has one Free Python service,
root `backend`, `/api/v1/health/`, automatic deploy enabled, and environment names
with `sync: false` (no values, including no secrets). Region is `oregon`: confirm
that it offers Free instances and choose the nearest supported region **before**
creation; the current region menu/schema is UNVERIFIED offline.

Render build command (Linux, paths quoted):

```sh
python -m pip install --disable-pip-version-check -r "./requirements.lock" && python "./manage.py" check --deploy --fail-level ERROR && python "./manage.py" collectstatic --noinput
```

Render start command:

```sh
gunicorn --config "./config/gunicorn.py" "config.wsgi:application"
```

Gunicorn/WhiteNoise are already pinned at26.2.0/6.12.0 in the lock and dependency
register (MIT); no dependency or install was added. One `gthread` worker/two
threads keeps a single in-process quota ledger and limits memory duplication on
the proposed512MB instance; actual hosted memory is UNVERIFIED. Timeout60s,
graceful timeout45s, keepalive2s; the application deadline stays35s. Access log
uses method, **path without query**, status and duration only. Render's own edge
logs are outside this app's control; inspect their privacy/retention settings.
Do not place keys in incoming URLs. Provider keys stay in server environment.

The production command refuses APP_ENV=development. APP_ENV=production skips
backend/.env entirely. Missing SECRET_KEY, ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS or
TOMTOM_API_KEY fails startup; DEBUG defaults false and true is rejected. Hosts
must be bare explicit hostnames; CORS entries are exact HTTPS origins, with
explicit HTTP loopback development origins permitted. No wildcard/preview-domain
regex is allowed. CORS credentials are disabled. DRF has no session/auth backend,
no admin route and no database models; DATABASES={} uses Django's dummy backend.
Health and analysis require no database, SQLite file, migrations or persistent
disk. Successful weather cache/quota/throttle state is process-local and resets
on restart; no route/geocode persistence. Ephemeral storage is therefore suitable.

Production enables SSL redirects, secure/HttpOnly/SameSite=Lax cookie flags,
explicit CSRF trusted origins, nosniff, no-referrer, DENY framing and modest
HSTS3600s without subdomains/preload. API requests do not create session cookies;
CSRF middleware remains available for future non-exempt views. Set
TRUST_PROXY_SSL_HEADER=true only on Render's proxy-terminated service, after
confirming the platform overwrites X-Forwarded-Proto and prevents direct public
access to the Gunicorn port. Gunicorn itself trusts no forwarded client headers.
The liveness health path is provider-independent; readiness checks configuration,
not entitlement, provider reachability, quota or release readiness.

**Client-IP trust:** set API_TRUSTED_PROXY_CIDRS to the empty string/leave unset
initially. This exact safe value ignores X-Forwarded-For and uses REMOTE_ADDR.
The repo contains no verified Render ingress CIDR list/header guarantee; a guessed
10.0.0.0/8, outbound-IP list, or0.0.0.0/0 is **not** a substitute. On the host,
obtain the actual immediate ingress proxy CIDRs and header sanitation guarantee
from Render's documentation/support, then set only those comma-separated CIDRs.
Until that is verified, requests sharing a proxy share throttle limits; do not
claim per-user isolation. TLS header trust and client-IP trust are separate.
The trusted-chain algorithm is documented in [api.md](api.md). No trusted range
was invented or broadened in this task.

Effective non-secret diagnostics (Render Shell if available; otherwise a one-off
local process with equivalent environment): `python "./manage.py" deployment_settings`.
It uses an explicit allowlist, reports key **presence only**, and makes no network
request. Free Shell availability is UNVERIFIED; do not upgrade to obtain it.

## Every backend environment variable

R = required host input; O = optional with the approved default; P = platform
managed. The blueprint prompts for all40 app/runtime names; use these defaults
for optional numeric/boolean prompts rather than an empty value. For an optional
empty setting, omit it in the dashboard if an empty input is not supported.
Examples below are public placeholders, never real credentials.

| Name | Purpose | Required | Host value / example |
|---|---|---|---|
| APP_ENV | Strict production mode | R | `production` |
| DEBUG | Disable debug | O | `false` (default in production) |
| PYTHON_VERSION | Render runtime | R | `3.12.10` matches locally tested Python; host support UNVERIFIED |
| SECRET_KEY | Django signing secret | R secret | Generate a unique strong random value in your password manager/dashboard; >=50 chars; never copy the local key |
| TOMTOM_API_KEY | Server routing/geocoding credential | R secret | Your entitled account key; never a VITE variable |
| ALLOWED_HOSTS | Allowed backend Host headers | R | Assigned bare `SERVICE.onrender.com`; no scheme/path; Pages hostname does not belong here |
| CORS_ALLOWED_ORIGINS | Browser callers | R | Initial `https://localhost`; then `https://PROJECT.pages.dev,http://localhost:5173,http://127.0.0.1:5173` |
| TRUST_PROXY_SSL_HEADER | Trust Render TLS termination | R for Render | `true`, subject to the proxy guarantee above |
| API_TRUSTED_PROXY_CIDRS | Trusted client-IP proxy hops | O | Empty/unset until verified; only actual ingress CIDRs afterward |
| APP_VERSION | Health release label | O | `0.1.0` |
| ROUTING_PROVIDER | Approved adapter | O | `tomtom` |
| WEATHER_PROVIDER | Approved adapter | O | `open_meteo` |
| PROVIDER_CONNECT_TIMEOUT_SECONDS | Connection cap | O | `3` |
| ROUTING_READ_TIMEOUT_SECONDS | Routing read cap | O | `25` |
| WEATHER_READ_TIMEOUT_SECONDS | Weather read cap | O | `12` |
| GEOCODE_READ_TIMEOUT_SECONDS | Geocoding read cap | O | `8` |
| ANALYSIS_DEADLINE_SECONDS | Shared hard deadline | O | `35` |
| MAX_ROUTE_DISTANCE_MILES | Shortest-route demo envelope | O | `300`; precheck240mi; retain longer alternatives |
| PROVIDER_ATTEMPTS | Geocoding attempts, bounded transient retry | O | `2`; routing timeouts never retried |
| PROVIDER_REQUESTS_PER_SECOND | Shared start rate | O | `5` |
| PROVIDER_CALL_CONCURRENCY | Shared concurrent provider calls | O | `2` |
| PROVIDER_RETRY_BACKOFF_SECONDS | Geocoding retry delay | O | `0.5` |
| CACHE_NAMESPACE | Local weather cache namespace | O | `routeshield` |
| WEATHER_CACHE_TTL_SECONDS | Successful normalized weather TTL | O | `900` maximum |
| WEATHER_CACHE_MAX_ENTRIES | Bounded weather cache | O | `400` |
| OPEN_METEO_BASE_URL | Approved weather endpoint | O | `https://api.open-meteo.com/v1/forecast`, only after eligibility gate |
| OPEN_METEO_MODEL | Requested model | O | `best_match` |
| WEATHER_ATTEMPTS | Total batch attempts | O | `2`; read-timeout retry needs >=10s remaining |
| WEATHER_RETRY_BACKOFF_SECONDS | Weather retry delay | O | `0.5` |
| WEATHER_DAILY_QUOTA_UNITS | Best-effort UTC daily guard | O | `8000` |
| WEATHER_REQUEST_UNIT_LIMIT | Per-batch reservation guard | O | `200` |
| WEATHER_GUSTS_ENABLED | Display-only optional gusts | O | `false` |
| MAX_WEATHER_COORDINATES | Pooled-coordinate cap | O | `200`; legacy larger values are clamped |
| WEATHER_BATCH_SIZE | Coordinates per batch | O | `50` |
| WEATHER_BATCH_CONCURRENCY | Weather batch concurrency | O | `2` |
| ANALYSIS_RATE_LIMIT | Analysis requests per window/IP | O | `10` |
| ANALYSIS_RATE_WINDOW_SECONDS | Analysis window | O | `600` |
| GEOCODE_RATE_LIMIT | Geocoding requests per window/IP | O | `30` |
| GEOCODE_RATE_WINDOW_SECONDS | Geocoding window | O | `60` |
| SIMULATION_ENABLED | Explicit labeled presets | O | `false`; enable only intentionally for the demo |
| PORT | Render-assigned listener port | P | Render supplies it; fallback10000; do not copy a local port |

**Local override warning (inspected without printing credentials):** the current
backend/.env contains APP_ENV=development, DEBUG=true, TRUST_PROXY_SSL_HEADER=false
and MAX_WEATHER_COORDINATES=300. Do **not** copy those values to Render. Local
effective coordinates are already clamped to200. Routing25/connect3/geocode8/
deadline35 and throttles10/600,30/60 match. Weather12/envelope300 use defaults
because those entries are absent. Do not copy local ALLOWED_HOSTS, local-only
CORS origins as the entire production list, SECRET_KEY, test flags, cache files,
or the `.env` file itself. Set the production TomTom credential separately in
the dashboard. The actual `.env` and the pre-existing `.env.example` edit were
left untouched.

## Frontend environment and CSP

| Name | Purpose | Required | Host value / example |
|---|---|---|---|
| VITE_API_BASE_URL | Public build-time API prefix | R | `https://SERVICE.onrender.com/api/v1/` |
| NODE_VERSION | Cloudflare Node runtime | R host | `24` |
| VITE_MAP_STYLE_URL | Public map style | O | `https://tiles.openfreemap.org/styles/positron` |
| VITE_MAP_GLYPHS_URL | Map glyphs | O | `https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf` |
| VITE_MAP_SPRITE_URL | Map sprites | O | `https://tiles.openfreemap.org/sprites/ofm_f384/ofm` |
| VITE_MAP_OFFLINE | Intentional background-only test mode | O | `false`/unset in production |
| VITE_E2E | Development-only inspection hooks | O test only | Unset in production |
| VITE_MOTION_DISABLED | Development/E2E-only static motion | O test only | Unset in production |

Missing/HTTP/localhost/credential-bearing/query-bearing production API bases fail
the build clearly; the path must be `/api/v1/`. Only explicitly selected public
VITE names are embedded, never server credentials. Map endpoint overrides must
use tiles.openfreemap.org, matching the CSP. Changing the public API origin
requires a new frontend build, which regenerates dist/_headers automatically.

The generated Cloudflare `_headers` allows scripts only from self (external
theme-init.js, no inline/eval), workers from self/blob, connections only to self,
the exact API origin and https://tiles.openfreemap.org (style, tiles, glyphs,
sprites), images self/data/blob/OpenFreeMap, and fonts self. Inline **styles** are
necessary for React/MapLibre positioning; they do not permit inline scripts.
Objects/base/form submissions/framing are denied. Headers include nosniff,
strict-origin-when-cross-origin, camera/mic/geolocation/payment denial and DENY
framing. Hashed `/assets/*` cache immutably for one year; `/`, index.html and the
unhashed theme script use no-cache. There is no client pathname router requiring
a custom `_redirects`; current navigation/share state uses the root/query only.
Vite preview applies the same generated policy through local middleware, since
it does not interpret Cloudflare `_headers` itself. Edge header merging, HTTPS
redirects and caching must still be checked after deployment.

## Dashboard steps (manual; nothing below has been executed remotely)

1. **GitHub, after separate authorization.** Inspect whether the provided repo
   already exists before creating anything; do not create a duplicate. In GitHub,
   create an empty RouteShield repository only if needed (no README/license
   initialization), and authorize the next task to connect/push. The next task
   will first inspect `git status`, branch and existing remotes, then conditionally
   run `git remote add origin "https://github.com/AliHassan-15/RouteShield.git"`
   and `git push -u origin main`. If origin/history already exists, stop for the
   appropriate non-destructive reconciliation; never overwrite/force-push. Expected:
   main contains the reviewed commits/locks/blueprint, no PDF or `.env`.
2. **Render Blueprint.** Sign in, verify no-card Free eligibility/remaining
   allowance and the release gates, choose New → Blueprint (labels UNVERIFIED),
   connect the repo/main and select render.yaml. Confirm Python, backend root,
   Free plan, region, build/start commands, auto-deploy and health path. Fill all
   prompted variable names using the tables; secret values are entered by you.
   Use initial local-only HTTPS CORS until the Pages URL exists. Confirm the
   assigned service hostname and set ALLOWED_HOSTS to that bare hostname before
   expecting health success; if the initial build started before this is known,
   correct it and redeploy. Expected logs: locked packages installed, Django
   check summary, static files copied, Gunicorn listening/worker started. HSTS
   subdomain/preload warnings are intentional at the modest3600s setting; no
   Django configuration error is acceptable. No migrations/database are needed.
   Health should become green at `/api/v1/health/`; readiness should return ready.
3. **Copy Render URL.** Record the exact HTTPS service origin and health URL in
   your private deployment notes. Expected: liveness200 with version/status/check,
   HTTP redirects to HTTPS, no debug traceback. The URL must not contain a key.
4. **Cloudflare Pages.** In Workers & Pages → Create → Pages → Connect Git (menu
   wording UNVERIFIED), connect the repo/main. Root directory `frontend`; preset
   Vite if offered; build command `npm ci --no-audit --no-fund && npm run build`;
   output `dist` (relative to frontend). Set NODE_VERSION and VITE_API_BASE_URL
   from the frontend table for Production; configure Preview separately only if
   desired, with exact preview origins separately allowlisted on the backend.
   Never enter SECRET_KEY or TOMTOM_API_KEY here. Expected: pinned npm install,
   tsc/Vite/build-guard success, dist/_headers uploaded, deployment URL assigned.
5. **Copy Pages URL.** Record the canonical HTTPS `PROJECT.pages.dev` origin.
   Expected: the shell/map load. API CORS may remain unavailable until the next
   step; this is not a successful integrated deployment yet.
6. **Update Render.** Set CORS_ALLOWED_ORIGINS to that exact Pages origin plus
   only the explicit local development origins you need. ALLOWED_HOSTS stays the
   Render hostname (and approved backend custom hostname if any); do **not** put
   a full Pages URL or scheme in ALLOWED_HOSTS. Save/redeploy. Expected: allowed
   preflight/simple requests include that origin, disallowed origins get no
   allow-origin header, versioned health/validation work through the Pages app.
7. **Verify.** Run the smoke checker without --analysis first, review headers,
   then authorize one --analysis run only after eligibility gates are resolved.
   Perform the hosted desktop/mobile trip, route/checkpoint selection, heat
   endpoints/playback/no-network-on-scrub and source-label checks. Replace README
   live placeholders only after these pass; record real screenshots, payload
   sizes and provider counts. Local checks do not resolve DEPLOY-04/05/06.

## Smoke and local production diagnosis

From the repo root, PowerShell:

```powershell
& "./backend/.venv/Scripts/python.exe" "./scripts/smoke/hosted_smoke.py" "https://SERVICE.onrender.com" "https://PROJECT.pages.dev"
# Optional, explicit one real analysis; consumes provider quota. No automatic retry.
& "./backend/.venv/Scripts/python.exe" "./scripts/smoke/hosted_smoke.py" "https://SERVICE.onrender.com" "https://PROJECT.pages.dev" --analysis
```

Linux uses `"./backend/.venv/bin/python"` with the same quoted script/arguments.
The checker accepts backend origin or its /api/v1/ base, validates credential-free
HTTPS (loopback HTTP only for local testing), exits nonzero on failure and never
prints keys, transport URLs, response bodies or raw exception details. It checks
health/readiness, allowed/disallowed CORS, security/redirects, HTML/asset MIME/cache,
short-geocode validation and malformed analysis envelope/request ID. --analysis
sends exactly one Santa Monica Pier(34.0094,-118.4973) → City Hall(34.0537,-118.2428),
45000lb, now+3h/UTC POST, validates three routes/status/49 heat frames, and prints
wall, actual wire/raw bytes and separately computed gzip bytes. Gzip computation
is not a claim that the server transmitted gzip.

Offline test: an owned Django **development server** with production environment,
synthetic key and no provider requests, plus Vite production preview. Windows
cannot run Gunicorn; no Waitress is approved/installed. The `--local-proxy` flag
is restricted to loopback and sends X-Forwarded-Proto:https to emulate TLS
termination, testing strict settings/HSTS without TLS. It skips Vite's absent
edge HTTP redirect and real frontend→backend destination matching; both remain
hosted checks. No local `.env` is modified and no real key is used.

## Operations and current free-tier evidence

Manual redeploy: Render Manual Deploy → deploy reviewed commit; Pages retry/create
deployment for the reviewed commit. Auto-deploy is enabled after future pushes;
never push unreviewed secrets. Rollback: select a previously verified deployment
in each dashboard and use its rollback action if Free supports it; otherwise
deploy the previous reviewed Git commit through the normal pipeline after user
authorization. Retain compatible API/frontend versions and environment values.
Rollback availability/menu names are UNVERIFIED; avoid rewriting Git history.

Logs: Render service → Logs/build events; Pages deployment → build log; browser
Network/Console for CORS/CSP. Correlate safe X-Request-ID values. Do not paste
credentials, query-bearing upstream URLs or raw provider bodies into issues.
Rotate TomTom: confirm accepted plan, create replacement in the provider dashboard,
update TOMTOM_API_KEY **only on Render**, redeploy, run health/optional authorized
smoke, then revoke the old key after verification. Never commit it or put it in
Cloudflare. Rotation/revocation are manual future actions, not authorized here.

| Host | Offline official-page record | Current state / dashboard checks |
|---|---|---|
| Cloudflare Pages | D17 cites [official limits](https://developers.cloudflare.com/pages/platform/limits/):500 builds/month, one concurrent build | Current limits, Node24 support, build system/install behavior, Free eligibility/card requirement, bandwidth/file limits, `_headers` processing and rollback are **UNVERIFIED** offline; check dashboard/current official page |
| Render Free | D18 cites [official Free docs](https://render.com/docs/free):750 instance hours/workspace/month,15min idle sleep, about1min wake, ephemeral filesystem; included bandwidth/build minutes, suspension without payment method on exhaustion | Current512MB/CPU allowance, runtime/region availability, exact build/bandwidth caps, free-hour reset, required card and overage controls, proxy/header guarantees and Shell/rollback access are **UNVERIFIED** offline |

If Free allowance is exhausted, stop analyses/deploy attempts, inspect the usage
page/reset date and wait for reset or suspend the demo. Do not add a card, upgrade,
auto-switch provider/host or run keepalive pings. Tell reviewers about downtime;
an existing labeled synthetic walkthrough can explain behavior without claiming
the hosted service is available. Recheck no-charge controls before public sharing.

## Verification record

Executed2026-10-22 on Windows/Python3.12.10/Node24, from the spaced repository
path. `dev.py lint`: Ruff clean,98 files formatting-clean,14 domain files without
forbidden imports, frontend ESLint clean. Strict mypy:96 source files clean;
smoke script separately passes strict mypy/Ruff/format. The dedicated tsc run
initially rejected two Testing Library `exact` options accidentally copied from
Playwright; these were removed, four scoped App tests/ESLint passed, and the
production build's full `tsc --noEmit` then passed. Full suites ran once:
**1575 backend passed/2 skipped** (optional live smoke), **256 frontend passed in
15 files**. Exactly20 high-value unit cases were added (nine backend,11 frontend).
The initial scoped shell command used the wrong cwd-relative interpreter and was
corrected before tests ran; an encoding error in the first App edit and scoped
format/quote findings were corrected before the passing full tests/lint.

Full root build passed once: Django check, collectstatic (27 unmodified files,
49 post-processed), compileall, tsc/Vite and production guard. A preceding
Vite-only build was necessary to obtain the production baseline before the single
performance fix; no repeated full suite was run. The actual production Vite
configuration rejects both empty and localhost API bases before transformation.
Final Node gzip6 bytes: initial JS **115582** (index106668 +shared8914), lazy map
289423, worker144614, checkpoints6468, heat controls3131; CSS12647/10468/2004;
fonts30092+40404=70496 raw. Initial JS is within200000 bytes. The existing large
lazy-map chunk warning remains visible, not suppressed.

CI JSON/YAML syntax/path/command checks pass. CI still runs root lint/format/
purity, mypy/tsc, both suites and production artifacts on ubuntu-latest using the
exact `Projects New/RouteShield` checkout and lowercase backend/frontend paths.
Its build uses a public synthetic HTTPS API origin, and the new smoke script has
explicit Linux quality checks. TypeScript enforces case consistency. No new
shell script/shebang or .gitattributes is required. **No GitHub workflow was run.**

The production-settings Django development server started with synthetic
credentials; no local `.env` was loaded. `check --deploy --fail-level ERROR`
passed with intentional W005/W021 warnings (no HSTS subdomains/preload).
Non-secret diagnostics confirmed DEBUG=false, no database,12/25/35s,300mi,
200 coordinates and10/600,30/60 throttles. The offline smoke completed **29 PASS
assertions**, including health/readiness, both CORS paths/disallowed origins,
400 validation/request IDs, frontend security/asset MIME/cache and backend301
HTTPS redirect. It skipped frontend edge redirect and live --analysis. Server
request records confirmed **TomTom routing0/geocoding0, Open-Meteo0**. Gunicorn,
Linux execution, TLS termination, actual browser→hosted API, hosting edge logs,
memory/cold starts, quotas and account controls remain UNVERIFIED.

Production browser: Chromium156.0.8078.4,1440x1000, ANGLE (Intel, Intel(R) UHD
Graphics (0x00009A60) Direct3D11 vs_5_0 ps_5_0, D3D11), hardware rendering.
Typed worst fixture:3 routes/200 points/49 frames, synthetic all-blocked branch;
fixed historical forecast rows are test data, not current weather. Every API
response was intercepted. Real OpenFreeMap responses were33 before/40 after,
all200; both runs recorded **zero CSP violations, zero page errors and CLS0**.
The four production/warmup screenshots were visually inspected. Artifacts and
raw CPU traces are ignored under `output/playwright/deployment/`.

| Production arrival (~2.1s response-to-settle observation) | Median /p95 /max frame ms | Long tasks /maximum ms | Blocking time ms |
|---|---|---|---|
| Before single fix |8.2 /25.0 /124.9 |2 /109 |65 |
| After single fix |4.2 /16.7 /83.3 |2 /64 (other52) |16 |

The original DEV observation was8.4/37.6/183.4ms, max long task169ms. Production
improves these observations, but the DEV server does **not** explain every miss.
CPU samples within the original109ms React effect/commit task show forced focus
and layout (~26.6ms sampled focus), plus map/heat image readback/layer setup. The
single small fix defers results-heading focus until after its first paint, cancels
on replacement/unmount and never overrides newer user focus; a regression test
covers that guard. Final64ms task still includes results layout/offset reads
(~18.4ms sampled) and heat image readback (~9.7ms); another48.9ms rAF callback
within the52ms long task spends ~37.7ms sampled in WebGL getProgramParameter,
consistent with shader/program setup. Decode was not identified as the dominant
cost. Further batching of map/heat layer installation or shader prewarming is
deferred for user direction: it changes more lifecycle/state behavior than this
single small fix. **The >50ms long-task target remains missed.** Rounded p9516.7ms
sits on the frame-budget boundary; no broad60fps pass is claimed.

These are one traced run per build, with real basemap/driver/JIT variation and CPU
profiling overhead, not a controlled causal benchmark or hosted guarantee.
There was no second optimization, dependency install/audit, provider request,
account action, remote/push or deployment. Current free-tier/Blueprint/Pages
facts and ingress CIDRs still require the dashboard checks above. Staged review
and the single authorized local commit are reported separately.
