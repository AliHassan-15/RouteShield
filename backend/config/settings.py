"""Stateless, environment-driven Django settings; providers are not contacted."""

import os
from pathlib import Path

from config.environment import integer, load_environment_file, number, runtime_settings

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
    "routing": os.environ.get("ROUTING_PROVIDER", "tomtom"),
    "weather": os.environ.get("WEATHER_PROVIDER", "open_meteo"),
    "tomtom_api_key": os.environ.get("TOMTOM_API_KEY", ""),
    "connect_timeout_seconds": number(os.environ, "PROVIDER_CONNECT_TIMEOUT_SECONDS", 3),
    "routing_timeout_seconds": number(os.environ, "ROUTING_READ_TIMEOUT_SECONDS", 25),
    "weather_timeout_seconds": number(os.environ, "WEATHER_READ_TIMEOUT_SECONDS", 8),
    "geocode_timeout_seconds": number(os.environ, "GEOCODE_READ_TIMEOUT_SECONDS", 8),
    "analysis_deadline_seconds": number(os.environ, "ANALYSIS_DEADLINE_SECONDS", 35),
    "max_coordinates": integer(os.environ, "MAX_WEATHER_COORDINATES", 300),
    "batch_size": integer(os.environ, "WEATHER_BATCH_SIZE", 50),
    "concurrency": integer(os.environ, "WEATHER_BATCH_CONCURRENCY", 2),
    "max_retries": integer(os.environ, "PROVIDER_ATTEMPTS", 2) - 1,
    "requests_per_second": integer(os.environ, "PROVIDER_REQUESTS_PER_SECOND", 5),
    "call_concurrency": integer(os.environ, "PROVIDER_CALL_CONCURRENCY", 2),
    "retry_backoff_seconds": number(os.environ, "PROVIDER_RETRY_BACKOFF_SECONDS", 0.5),
}
# Configuration is prepared now; provider work/throttling belongs to later tasks.
ANALYSIS_RATE_LIMIT = integer(os.environ, "ANALYSIS_RATE_LIMIT", 10)
ANALYSIS_RATE_WINDOW_SECONDS = integer(os.environ, "ANALYSIS_RATE_WINDOW_SECONDS", 600)
GEOCODE_RATE_LIMIT = integer(os.environ, "GEOCODE_RATE_LIMIT", 30)
GEOCODE_RATE_WINDOW_SECONDS = integer(os.environ, "GEOCODE_RATE_WINDOW_SECONDS", 60)
