"""Versioned foundation routes."""

from django.urls import path

from apps.routing.views import AnalysisView, GeocodeView, health

urlpatterns = [
    path("health/", health, name="health"),
    path("route-analysis/", AnalysisView.as_view(), name="route-analysis"),
    path("geocode/", GeocodeView.as_view(), name="geocode"),
]
