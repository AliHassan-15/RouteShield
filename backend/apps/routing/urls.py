"""Versioned foundation routes."""

from django.urls import path

from apps.routing.views import health

urlpatterns = [path("health/", health, name="health")]
