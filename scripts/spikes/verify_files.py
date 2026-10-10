"""Offline spike verification and exact-secret search, with values withheld."""
import json
import re
import subprocess
import sys
from urllib.parse import quote

from common import FIXTURES, KEY, OUT, ROOT, save
from route_analysis import timing

patterns = [re.compile(rb"\b[A-Za-z0-9]{32}\b"), re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
            re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
            re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
            re.compile(rb"[?&]key=[A-Za-z0-9]{12,}"),
            re.compile(rb'''(?i)(?:api_key|token|password|secret)\s*[:=]\s*["'][A-Za-z0-9+/_-]{16,}["']''')]
paths = [ROOT / "docs/provider-findings.md"]
paths += [p for folder in (OUT.parent, FIXTURES) for p in folder.rglob("*") if p.is_file()]
for path in paths:
    content = path.read_bytes()
    assert all(not secret or secret.encode() not in content for secret in (KEY, quote(KEY, safe=""))), f"Exact secret detected in {path.name}; value withheld"
    assert not any(p.search(content) for p in patterns), f"Potential credential pattern in {path.name}; value withheld"
sources = list(OUT.parent.glob("*.py"))+list(OUT.parent.glob("*.mjs"))
for path in sources:
    assert len(path.read_text().splitlines()) <= 80, path.name
    if path.suffix == ".py":
        compile(path.read_text(), str(path), "exec")
routes = json.loads((FIXTURES / "routing_three_routes.json").read_text())
assert routes["_fixture"]["live_result"] is False and len(routes["routes"]) == 3
assert all(timing(route)["usable"] for route in routes["routes"])
for name in ("weather_batch.json", "weather_null.json"):
    for obj in json.loads((FIXTURES / name).read_text()):
        rows = obj["hourly"]
        assert len({len(values) for values in rows.values()}) == 1
        assert all(b-a == 3600 for a, b in zip(rows["time"], rows["time"][1:]))
null = json.loads((FIXTURES / "weather_null.json").read_text())[0]["hourly"]
assert all(null[field][0] is not None and null[field][1:] == [None, None] for field in ("wind_speed_10m", "rain", "showers", "snowfall"))
assert json.loads((FIXTURES / "quota_exceeded.json").read_text())["body"] is None
ledger = json.loads((OUT / "requests.json").read_text())
counts = {provider: sum(row["provider"] == provider for row in ledger) for provider in ("tomtom", "open_meteo")}
assert counts["tomtom"] <= 40 and counts["open_meteo"] <= 25
assert json.loads((OUT / "metric_checks.json").read_text())["passed"] == 8
changed = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode().split("\0")
changed += subprocess.check_output(["git", "diff", "HEAD", "--name-only", "-z"], cwd=ROOT).decode().split("\0")
assert all(not p or p == "docs/provider-findings.md" or p.startswith(("scripts/spikes/", "backend/tests/fixtures/")) for p in changed)
result = {"exact_key_present_in_memory": bool(KEY), "files_scanned_including_ignored_spike_caches": len(paths), "credential_matches": 0, "scripts_compiled_or_syntax_counted": len(sources), "all_scripts_at_most_80_lines": True, "fixture_checks": "PASS", "metric_controls": 8, "approved_scope": "PASS", "api_attempts": counts}
if "--staged" in sys.argv:
    staged = subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"], cwd=ROOT).decode().split("\0")
    for path in filter(None, staged):
        content = subprocess.check_output(["git", "show", ":"+path], cwd=ROOT)
        assert all(not secret or secret.encode() not in content for secret in (KEY, quote(KEY, safe=""))), "Exact secret in index; value withheld"
        assert not any(p.search(content) for p in patterns), "Possible credential in index; value withheld"
    result["staged_review"] = "PASS"
    result["staged_file_count"] = len(list(filter(None, staged)))
save(OUT / "verification.json", result)
print(json.dumps(result))
