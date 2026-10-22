"""Print an explicit allowlist of effective configuration, never credential values."""

import json

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Print effective non-secret deployment settings; no provider calls."

    def handle(self, *args: object, **options: object) -> None:
        names = (
            "APP_ENV",
            "APP_VERSION",
            "DEBUG",
            "ALLOWED_HOSTS",
            "CORS_ALLOWED_ORIGINS",
            "CSRF_TRUSTED_ORIGINS",
            "SECURE_SSL_REDIRECT",
            "SECURE_PROXY_SSL_HEADER",
            "SECURE_HSTS_SECONDS",
            "API_TRUSTED_PROXY_CIDRS",
            "ANALYSIS_RATE_LIMIT",
            "ANALYSIS_RATE_WINDOW_SECONDS",
            "GEOCODE_RATE_LIMIT",
            "GEOCODE_RATE_WINDOW_SECONDS",
            "SIMULATION_ENABLED",
        )
        safe = {name: getattr(settings, name) for name in names}
        safe["provider_limits"] = {
            key: value
            for key, value in settings.PROVIDER_CONFIG.items()
            if key not in {"tomtom_api_key", "weather_base_url"}
        }
        safe["tomtom_key_present"] = bool(settings.PROVIDER_CONFIG["tomtom_api_key"])
        safe["database_required"] = False
        self.stdout.write(json.dumps(safe, sort_keys=True, indent=2))
