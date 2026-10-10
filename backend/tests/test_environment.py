"""Meaningful negative tests for production startup safety."""

import os
import subprocess
import sys

import pytest
from config.environment import runtime_settings
from django.core.exceptions import ImproperlyConfigured

PUBLIC_TEST_VALUE = "test-only-public-configuration-fixture-0123456789-abcdefghijklmnopqrstuvwxyz"


def production_values() -> dict[str, str]:
    """Return public synthetic configuration, never a real secret."""
    return {
        "APP_ENV": "production",
        "DEBUG": "false",  # A local development .env must not change this fixture.
        "SECRET_KEY": PUBLIC_TEST_VALUE,
        "ALLOWED_HOSTS": "api.example.test",
        "CORS_ALLOWED_ORIGINS": "https://app.example.test",
    }


@pytest.mark.parametrize("missing", ["SECRET_KEY", "ALLOWED_HOSTS", "CORS_ALLOWED_ORIGINS"])
def test_missing_production_configuration(missing: str) -> None:
    """Production cannot silently fall back to development configuration."""
    values = production_values()
    del values[missing]
    with pytest.raises(ImproperlyConfigured, match=missing):
        runtime_settings(values)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("DEBUG", "true"),
        ("ALLOWED_HOSTS", "*"),
        ("SECRET_KEY", "replace-me"),
        ("CORS_ALLOWED_ORIGINS", "http://app.example.test"),
        ("CORS_ALLOWED_ORIGINS", "https://app.example.test/path"),
    ],
)
def test_invalid_production_configuration(key: str, value: str) -> None:
    """Explicit but unsafe production configuration is rejected."""
    values = production_values()
    values[key] = value
    with pytest.raises(ImproperlyConfigured):
        runtime_settings(values)


def test_production_flags() -> None:
    """Valid configuration applies strict production settings."""
    settings = runtime_settings(production_values())
    assert settings["DEBUG"] is False
    assert settings["SECURE_SSL_REDIRECT"] is True
    assert settings["CSRF_COOKIE_SECURE"] is True


def test_actual_startup_fails_without_secret() -> None:
    """Exercise a fresh Django process rather than only a parser function."""
    values = dict(os.environ)
    values.update(production_values())
    values["SECRET_KEY"] = ""  # Also prevents an optional local .env from filling it.
    result = subprocess.run(
        [sys.executable, "manage.py", "check"],
        env=values,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "SECRET_KEY is required for production" in result.stderr
