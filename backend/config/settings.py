"""Stateless, environment-driven Django settings; providers are not contacted."""

import os
from pathlib import Path

from domain.route_policy import DEFAULT_MAX_ROUTE_DISTANCE_MILES

from config.environment import (
    boolean,
    integer,
    load_environment_file,
    number,
    provider_selector,
    runtime_settings,
)

BASE_DIR = Path(__file__).resolve().parent.parent
load_environment_file(BASE_DIR / ".env")
globals().update(runtime_settings(os.environ))
APP_VERSION = os.environ.get("APP_VERSION", "0.1.0")

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "apps.routing",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.routing.middleware.APIRequestMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
DATABASES: dict[str, object] = {}
USE_TZ = True
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
CORS_ALLOW_ALL_ORIGINS = False
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
}
DATA_UPLOAD_MAX_MEMORY_SIZE = 16 * 1024
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": os.environ.get("CACHE_NAMESPACE", "routeshield"),
        "TIMEOUT": integer(os.environ, "WEATHER_CACHE_TTL_SECONDS", 900),
    },
}
PROVIDER_CONFIG = {
    "routing": provider_selector(os.environ, "ROUTING_PROVIDER", "tomtom"),
    "weather": provider_selector(os.environ, "WEATHER_PROVIDER", "open_meteo"),
    "tomtom_api_key": os.environ.get("TOMTOM_API_KEY", ""),
    "connect_timeout_seconds": number(os.environ, "PROVIDER_CONNECT_TIMEOUT_SECONDS", 3),
    "routing_timeout_seconds": number(os.environ, "ROUTING_READ_TIMEOUT_SECONDS", 25),
    "weather_timeout_seconds": number(os.environ, "WEATHER_READ_TIMEOUT_SECONDS", 12),
    "geocode_timeout_seconds": number(os.environ, "GEOCODE_READ_TIMEOUT_SECONDS", 8),
    "analysis_deadline_seconds": number(os.environ, "ANALYSIS_DEADLINE_SECONDS", 35),
    "max_route_distance_miles": number(
        os.environ, "MAX_ROUTE_DISTANCE_MILES", DEFAULT_MAX_ROUTE_DISTANCE_MILES
    ),
    # Legacy local overrides cannot expand the approved unique-coordinate cap.
    "max_coordinates": min(integer(os.environ, "MAX_WEATHER_COORDINATES", 200), 200),
    "batch_size": integer(os.environ, "WEATHER_BATCH_SIZE", 50),
    "concurrency": integer(os.environ, "WEATHER_BATCH_CONCURRENCY", 2),
    "max_retries": integer(os.environ, "PROVIDER_ATTEMPTS", 2) - 1,
    "requests_per_second": integer(os.environ, "PROVIDER_REQUESTS_PER_SECOND", 5),
    "call_concurrency": integer(os.environ, "PROVIDER_CALL_CONCURRENCY", 2),
    "retry_backoff_seconds": number(os.environ, "PROVIDER_RETRY_BACKOFF_SECONDS", 0.5),
    "weather_base_url": os.environ.get(
        "OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1/forecast"
    ),
    "weather_model": os.environ.get("OPEN_METEO_MODEL", "best_match"),
    "weather_max_retries": integer(os.environ, "WEATHER_ATTEMPTS", 2) - 1,
    "weather_retry_backoff_seconds": number(os.environ, "WEATHER_RETRY_BACKOFF_SECONDS", 0.5),
    "weather_daily_quota_units": integer(os.environ, "WEATHER_DAILY_QUOTA_UNITS", 8000),
    "weather_request_unit_limit": integer(os.environ, "WEATHER_REQUEST_UNIT_LIMIT", 200),
    "weather_cache_ttl_seconds": integer(os.environ, "WEATHER_CACHE_TTL_SECONDS", 900),
    "weather_cache_max_entries": integer(os.environ, "WEATHER_CACHE_MAX_ENTRIES", 400),
    "weather_gusts": boolean(os.environ, "WEATHER_GUSTS_ENABLED", False),
}
# Per-process DRF throttles are friction, not a distributed DoS defense.
ANALYSIS_RATE_LIMIT = integer(os.environ, "ANALYSIS_RATE_LIMIT", 10)
ANALYSIS_RATE_WINDOW_SECONDS = integer(os.environ, "ANALYSIS_RATE_WINDOW_SECONDS", 600)
GEOCODE_RATE_LIMIT = integer(os.environ, "GEOCODE_RATE_LIMIT", 30)
GEOCODE_RATE_WINDOW_SECONDS = integer(os.environ, "GEOCODE_RATE_WINDOW_SECONDS", 60)
API_TRUSTED_PROXY_CIDRS = tuple(
    value.strip()
    for value in os.environ.get("API_TRUSTED_PROXY_CIDRS", "").split(",")
    if value.strip()
)
CORS_EXPOSE_HEADERS = ["X-Request-ID", "Retry-After"]
# Structured API records replace Django's status/path logging; no traceback/body logging.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"api_json": {"format": "%(message)s"}},
    "handlers": {
        "discard": {"class": "logging.NullHandler"},
        "api_console": {"class": "logging.StreamHandler", "formatter": "api_json"},
    },
    "loggers": {
        "django.request": {"handlers": ["discard"], "propagate": False},
        "django.server": {"handlers": ["discard"], "propagate": False},
        "routeshield.requests": {"handlers": ["api_console"], "level": "INFO", "propagate": False},
    },
}
