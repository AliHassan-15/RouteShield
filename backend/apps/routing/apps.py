"""Application registration without database models."""

from django.apps import AppConfig


class RoutingConfig(AppConfig):
    """Register the API package."""

    name = "apps.routing"
