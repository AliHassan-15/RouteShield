"""Production safety and the dependency-free smoke checker, with synthetic data only."""

import importlib.util
import io
import json
import runpy
from pathlib import Path

import pytest
from django.core.management import call_command

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "hosted_smoke", ROOT / "scripts/smoke/hosted_smoke.py"
)
assert spec and spec.loader
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


@pytest.mark.parametrize(
    "url",
    [
        "http://public.example.test",
        "https://user:pass@example.test",
        "https://example.test/?key=synthetic",
    ],
)
def test_smoke_rejects_unsafe_targets(url: str) -> None:
    with pytest.raises(ValueError):
        smoke.base_url(url)


def test_asset_parser_checks_only_loadable_references() -> None:
    parser = smoke.Assets()
    parser.feed(
        '<script src="/assets/app.js"></script><link rel="stylesheet" href="/assets/app.css"><a href="https://example.test">credit</a>'
    )
    assert parser.paths == {"/assets/app.js", "/assets/app.css"}


def test_smoke_error_contract_requires_correlation() -> None:
    raw = b'{"error":{"code":"VALIDATION_ERROR","message":"Invalid","details":{}}}'
    assert not smoke.error_shape(raw, {})
    assert smoke.error_shape(raw, {"x-request-id": "synthetic-request-id"})


def test_gunicorn_bounds_and_query_free_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.delenv("APP_ENV", raising=False)
    config = runpy.run_path(str(ROOT / "backend/config/gunicorn.py"))
    assert config["workers"] == 1 and config["threads"] == 2
    assert config["timeout"] > 35 and config["graceful_timeout"] > 35
    assert "%(U)s" in config["access_log_format"]
    assert all(token not in config["access_log_format"] for token in ["%(r)s", "%(q)s", "%(h)s"])


def test_diagnostics_allowlist_omits_secret_values(settings: object) -> None:
    stream = io.StringIO()
    call_command("deployment_settings", stdout=stream)
    output = json.loads(stream.getvalue())
    assert "SECRET_KEY" not in output
    assert "tomtom_api_key" not in output["provider_limits"]
    assert "weather_base_url" not in output["provider_limits"]
    assert output["database_required"] is False
