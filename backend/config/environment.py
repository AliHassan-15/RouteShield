"""Small environment parsers without an extra configuration dependency."""

import os
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured


def load_environment_file(path: Path) -> None:
    """Read optional plain KEY=value entries; existing process values always win."""
    if not path.is_file():
        return
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key.strip().isidentifier():
            raise ImproperlyConfigured(f"Invalid environment entry at line {number}.")
        value = value.strip()
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ImproperlyConfigured(f"Unclosed environment value at line {number}.")
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def boolean(values: Mapping[str, str], key: str, default: bool) -> bool:
    """Parse explicit booleans and reject misspelled values."""
    value = values.get(key, str(default)).lower()
    if value not in {"true", "false", "1", "0"}:
        raise ImproperlyConfigured(f"{key} must be true/false or 1/0.")
    return value in {"true", "1"}


def provider_selector(values: Mapping[str, str], key: str, approved: str) -> str:
    """Reject unsupported adapters instead of silently ignoring the configured choice."""
    if values.get(key, approved) != approved:
        raise ImproperlyConfigured(f"{key} must be {approved}.")
    return approved


def number(values: Mapping[str, str], key: str, default: float) -> float:
    """Parse positive, finite transport limits."""
    import math

    try:
        value = float(values.get(key, str(default)))
    except ValueError as error:
        raise ImproperlyConfigured(f"{key} must be numeric.") from error
    if not math.isfinite(value) or value <= 0:
        raise ImproperlyConfigured(f"{key} must be finite and positive.")
    return value


def integer(values: Mapping[str, str], key: str, default: int) -> int:
    """Parse positive integer configuration values."""
    value = number(values, key, float(default))
    if not value.is_integer():
        raise ImproperlyConfigured(f"{key} must be an integer.")
    return int(value)


def runtime_settings(values: Mapping[str, str]) -> dict[str, object]:
    """Validate runtime settings, failing closed for production or DEBUG=False."""
    environment = values.get("APP_ENV", "development")
    if environment not in {"development", "production"}:
        raise ImproperlyConfigured("APP_ENV must be development or production.")
    debug = boolean(values, "DEBUG", environment == "development")
    if environment == "production" and debug:
        raise ImproperlyConfigured("Production requires DEBUG=False.")
    strict = environment == "production" or not debug
    secret = values.get("SECRET_KEY", "")
    hosts_raw = values.get("ALLOWED_HOSTS", "")
    cors_raw = values.get("CORS_ALLOWED_ORIGINS", "")
    if strict:
        for key, value in (
            ("SECRET_KEY", secret),
            ("ALLOWED_HOSTS", hosts_raw),
            ("CORS_ALLOWED_ORIGINS", cors_raw),
        ):
            if not value.strip():
                raise ImproperlyConfigured(f"{key} is required for production.")
        if len(secret) < 50 or secret.startswith(("insecure-", "replace-")):
            raise ImproperlyConfigured("Production SECRET_KEY must be a strong external secret.")
    else:
        secret = secret or "insecure-development-placeholder-not-a-real-secret"
        hosts_raw = hosts_raw or "localhost,127.0.0.1,[::1]"
        cors_raw = cors_raw or "http://localhost:5173,http://127.0.0.1:5173"
    hosts = [entry.strip() for entry in hosts_raw.split(",") if entry.strip()]
    origins = [entry.strip() for entry in cors_raw.split(",") if entry.strip()]
    if strict and any("*" in host for host in hosts):
        raise ImproperlyConfigured("Production ALLOWED_HOSTS must list explicit hosts.")
    for origin in origins:
        parsed = urlsplit(origin)
        if (
            not parsed.hostname
            or parsed.scheme not in ({"https"} if strict else {"http", "https"})
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or "*" in origin
        ):
            raise ImproperlyConfigured("CORS_ALLOWED_ORIGINS must contain explicit origins.")
    if not hosts or not origins:
        raise ImproperlyConfigured("ALLOWED_HOSTS and CORS_ALLOWED_ORIGINS cannot be empty.")
    return {
        "APP_ENV": environment,
        "APP_VERSION": values.get("APP_VERSION", "0.1.0"),
        "DEBUG": debug,
        "SECRET_KEY": secret,
        "ALLOWED_HOSTS": hosts,
        "CORS_ALLOWED_ORIGINS": origins,
        "SECURE_SSL_REDIRECT": strict,
        "SESSION_COOKIE_SECURE": strict,
        "CSRF_COOKIE_SECURE": strict,
        "SECURE_HSTS_SECONDS": 3600 if strict else 0,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": False,
        "SECURE_HSTS_PRELOAD": False,
        "SECURE_PROXY_SSL_HEADER": (
            ("HTTP_X_FORWARDED_PROTO", "https")
            if boolean(values, "TRUST_PROXY_SSL_HEADER", False)
            else None
        ),
        "SIMULATION_ENABLED": boolean(values, "SIMULATION_ENABLED", False),
    }
