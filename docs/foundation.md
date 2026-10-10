# Project foundation verification

Observed on 2026-10-10 in Windows PowerShell at `D:/Projects New/RouteShield`.
Python 3.12.10, Node 24.18.0, npm 11.16.0; project-local venv/dependencies/caches.
This implements only configuration, health, a minimal React shell and tooling.
No risk/route/weather/geocode logic, provider request or map package exists.
The assessment stays on disk at `Requirements/fs-assessment-spotter.pdf`, ignored.
README intentionally contains section headings only for a later documentation task.

## Usage and boundaries

Run the single entry point from the repository root; exact commands are in
[AGENTS.md section 10](../AGENTS.md#10-commands). Setup installs the Python lock
and uses npm ci with the frontend lock. Subsequent commands use the explicit
backend venv interpreter. Subprocess argument lists preserve spaces on Windows
and Linux; CI deliberately checks out into `Projects New/RouteShield`.
`run` starts Django at http://127.0.0.1:8000 and Vite at http://127.0.0.1:5173.
Ctrl+C terminates its own children. Browser smoke requires both servers running.
Stop servers before setup: npm ci must replace native Node modules, which Windows
locks while Vite is using them.

Backend reads optional user-created `backend/.env` plain KEY=value lines;
process environment takes precedence, quoted values are supported, interpolation
and shell evaluation are not. Vite reads its normal user-created local env files.
Neither real .env files nor real keys were created. Safe documented examples:
[backend](../backend/.env.example), [frontend](../frontend/.env.example).
Only `VITE_API_BASE_URL` belongs in the frontend example; provider keys stay server-side.
Local defaults need no secret. Production (or DEBUG=false) fails at startup for
missing/weak SECRET_KEY, missing hosts/origins, wildcard hosts or insecure CORS;
APP_ENV=production forbids DEBUG=true and enables HTTPS/secure-cookie settings.
Trust forwarded TLS headers only when explicitly enabled behind a trusted proxy.
Provider/cache/budget/throttle settings are prepared; adapters/throttles are future work.
TomTom credentials are not required by health; no provider-backed endpoint exists yet.

Liveness GET `/api/v1/health/`: status=ok, version=0.1.0, check=liveness.
Readiness GET `/api/v1/health/?ready=1`: status=ready, version=0.1.0, check=readiness.
Both return 200/no-store and depend only on the running configured process.
Readiness does not validate provider access or analysis readiness. POST returns 405.
The shell has loading/healthy/unreachable states, a five-second request deadline,
no automatic retry/refetch/polling, and an explicit Check again control.
Domain import check rejects Django/HTTP/socket/config/API/provider imports; the
domain package is currently empty. This is a cheap static boundary guard, not a
complete guarantee against dynamic imports or every form of I/O.

## Inspected verification results

| Check | Actual result |
|---|---|
| Single setup command with pinned locks | Exit 0; pip requirements satisfied, npm ci installed 191 packages |
| Backend pytest | 15 passed, no warnings in final run |
| Ruff lint/format and domain guard | Pass; 22 Python files formatted; 1 domain file inspected |
| Strict mypy/django-stubs | No issues in 21 source files |
| Frontend non-watch Vitest/Testing Library | 3 tests passed in 1 file |
| ESLint/format rules | Exit 0, zero warnings |
| Strict tsc | Exit 0 |
| Backend artifact build | Django check: 0 issues; collectstatic and compileall exit 0 |
| Frontend production build | 62 modules; JS 254.17 kB / gzip 78.72 kB; CSS 0.29 kB / gzip 0.22 kB |
| Both development servers | Django 5.2.18 and Vite 8.3.4 started; Django system check: 0 issues |
| Actual health/CORS requests | Liveness/readiness 200; explicit allow-origin http://127.0.0.1:5173 |
| Real Chromium Playwright smoke | 1 passed; actual HTTP 200 and visible Healthy — version 0.1.0 |
| Screenshot | `output/playwright/health.png` captured and visually inspected; ignored local artifact |
| CI syntax/commands/exact case/spaced path | JSON-form YAML parses; local assertions pass |
| Advisory audits | OSV: 32 PyPI packages, 0 affected; npm: 0 vulnerabilities |

Initial lint/type issues were corrected before these final checks. Initial OSV
found pip25.0.1 affected by published advisories; existing local pip was updated
to 26.2.1, locked, and re-audited cleanly. The first browser attempt timed out
because sandboxed localhost sockets were inaccessible; rerunning both dev
servers/browser outside that sandbox passed. Only a harmless Playwright terminal
NO_COLOR/FORCE_COLOR warning remained. No application check remains failing.
One repeated setup attempt encountered a Vite-held Windows native-module lock;
stopping the owned servers and rerunning the documented setup completed successfully.

Linux CI/Gunicorn execution, hosted verification, live provider/quota measurement,
domain/adapter/trip/map/heatmap acceptance criteria and full trip e2e remain
unexecuted; they belong to later authorized tasks. Local CI syntax validation
does not claim a GitHub Actions run. No remote, push or deployment is authorized.
Dependency versions/licenses/size methodology are in [dependencies.md](dependencies.md).
Elapsed working time was not provided by the user and is not estimated.

## AGENTS.md change summary

- Stack guidance: explicitly defer MapLibre installation to the map task.
- Layout: identify existing foundation vs future features; add locks/config/examples,
  e2e, tools, CI, dev.py and the two foundation documentation files.
- Health contract: record version/status/check and limited readiness semantics.
- Commands: replace every TBD template with the verified single-entry commands,
  explicit Windows/Linux interpreter paths and honest Linux execution status.
  Name the actual tools, require non-watch Vitest, keep downloads/caches local,
  remove the unverified Gunicorn hosting command, and retain the documentation-task gate.

Local staged-file review and commit outcome are reported in the final task response.
