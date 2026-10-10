"""Throwaway spike transport: allowlist, conservative budgets, key-safe evidence."""
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "evidence"
OUT.mkdir(exist_ok=True)
FIXTURES = ROOT / "backend/tests/fixtures/providers"
FIXTURES.mkdir(parents=True, exist_ok=True)
env = ROOT / "backend/.env"
values = {}
if env.is_file():
    for line in env.read_text(encoding="utf-8-sig").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
KEY = os.environ.get("TOMTOM_API_KEY") or values.get("TOMTOM_API_KEY", "")
HOSTS = {"tomtom": "api.tomtom.com", "open_meteo": "api.open-meteo.com"}
LIMITS = {"tomtom": 40, "open_meteo": 25}
LEDGER = OUT / "requests.json"


def scrub(value):
    text = json.dumps(value, ensure_ascii=False)
    for secret in (KEY, quote(KEY, safe="")):
        if secret:
            text = text.replace(secret, "[REDACTED]")
    text = re.sub(r'https?[^\s"\\<>]+', "[URL OMITTED]", text)
    return json.loads(text)


def save(path, value):
    path.write_text(json.dumps(scrub(value), indent=2), encoding="utf-8")


def request(provider, label, path, params, fake_key=False):
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else []
    if sum(row["provider"] == provider for row in ledger) >= LIMITS[provider]:
        raise SystemExit("Provider request budget exhausted.")
    pairs = list(params)
    if provider == "tomtom":
        if not KEY:
            raise SystemExit("TomTom key is missing; no request made.")
        pairs.append(("key", "invalid-test-key" if fake_key else KEY))
    row = {"provider": provider, "label": label, "sent_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    ledger.append(row)
    save(LEDGER, ledger)  # Reserve before network; failed attempts count conservatively.
    start = time.perf_counter()
    try:
        with httpx.Client(timeout=httpx.Timeout(60, connect=3), follow_redirects=False) as client:
            response = client.get("https://" + HOSTS[provider] + path, params=pairs)
        row.update(status=response.status_code, seconds=round(time.perf_counter() - start, 3), bytes=len(response.content))
        try:
            body = scrub(response.json())
        except ValueError:
            body = {"non_json_body": scrub(response.text), "bytes": len(response.content)}
        row["usage_metadata"] = {k: v for k, v in response.headers.items() if any(t in k.lower() for t in ("ratelimit", "rate-limit", "quota", "usage", "retry-after"))}
        row["response_metadata"] = {k: response.headers.get(k) for k in ("cache-control", "content-type")}
    except (httpx.HTTPError, OSError) as error:
        row.update(status="NETWORK_ERROR", error_type=type(error).__name__, seconds=round(time.perf_counter() - start, 3))
        row["safe_reason"] = scrub(str(error))  # Scrub before saving/printing any diagnostic.
        body = {"error_type": type(error).__name__}
    save(LEDGER, ledger)
    print(json.dumps(scrub(row)), flush=True)
    return row, body
