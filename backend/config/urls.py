"""Only the foundation health API is available in this task."""

from django.urls import include, path

urlpatterns = [path("api/v1/", include("apps.routing.urls"))]
