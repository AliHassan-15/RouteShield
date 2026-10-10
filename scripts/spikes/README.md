# Throwaway provider spike

**VERIFIED:** These scripts use existing project-local HTTPX and Playwright. No packages were installed. Their output is scrubbed; the TomTom key is read from process environment or the ignored `backend/.env` and never printed. API budgets are reserved before each attempt in `evidence/requests.json`; run API probes sequentially because this ledger is intentionally not a concurrent task runner.

**VERIFIED:** The recorded spike ran on 2026-10-10. `evidence/requests.json`, `routing_metrics.json`, `weather_analysis.json`, `coordinate_budget.json`, `accounting.json` and documentation metadata preserve the numeric findings. Bulk raw responses and the full-page pricing screenshot were temporary inputs, removed before commit. Real TomTom payloads were replaced with user-approved synthetic fixtures.

**VERIFIED:** `metric_checks.py`, `fixture_builder.py` and `verify_files.py` run offline. The route/weather analyses describe the commands actually executed while their raw inputs existed; they are not a promise that removed inputs remain in Git. Live probes spend quota. `route_probe.py` and `geocode_probe.py` only record raw TomTom responses with `--record-raw`; using that option requires confirmed storage permission. `weather_probe.py` fails explicitly when its real route-corridor input is absent instead of inventing a route. Do not reset the ledger to bypass its caps.

**UNVERIFIED:** These compact scripts are not production adapters and have no production retry, timeout, concurrency or typing guarantees. Never import them into application code. See [provider-findings.md](../../docs/provider-findings.md) for release gates and proposed decisions.
