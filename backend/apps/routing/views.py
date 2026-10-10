"""Thin health, analysis and geocoding endpoints with centralized safe errors."""

from math import ceil
from typing import cast

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from rest_framework.exceptions import MethodNotAllowed, Throttled  # type: ignore[import-untyped]
from rest_framework.request import Request  # type: ignore[import-untyped]
from rest_framework.response import Response  # type: ignore[import-untyped]
from rest_framework.views import APIView  # type: ignore[import-untyped]

from apps.routing.errors import APIError
from apps.routing.middleware import context_for, record_simulation_attempt, service_for
from apps.routing.throttles import AnalysisThrottle, GeocodeThrottle
from apps.routing.validation import parse_json


class SafeAPIView(APIView):  # type: ignore[misc]
    """Central fixed errors, including unexpected exceptions, without traceback disclosure."""

    def handle_exception(self, exc: Exception) -> Response:
        if isinstance(exc, APIError):
            error = exc
        elif isinstance(exc, Throttled):
            error = APIError("THROTTLED", retry_after=max(1, ceil(exc.wait or 1)))
        elif isinstance(exc, MethodNotAllowed):
            error = APIError("METHOD_NOT_ALLOWED")
        else:
            error = APIError("INTERNAL_ERROR")
        payload = error.envelope()
        if self.request.path == "/api/v1/route-analysis/":
            payload.update(
                {
                    "is_simulation": getattr(self.request._request, "api_simulated", False),
                    "simulation_scenario": getattr(self.request._request, "api_scenario", None),
                }
            )
        response = Response(payload, status=error.status)
        if error.retry_after is not None:
            response["Retry-After"] = str(error.retry_after)
        return response


class AnalysisView(SafeAPIView):
    throttle_classes = [AnalysisThrottle]
    http_method_names = ["post"]

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        """Keep explicit simulation identity even when throttling rejects the request."""
        if request.method == "POST":
            raw = request._request
            value = parse_json(cast(bytes, raw.__dict__["api_body"]))
            record_simulation_attempt(raw, value)
            raw.__dict__["api_payload"] = value
        super().initial(request, *args, **kwargs)

    def post(self, request: Request) -> Response:
        raw = request._request
        value = raw.__dict__["api_payload"]
        return Response(service_for(raw).analyze(value, context_for(raw)))


class GeocodeView(SafeAPIView):
    throttle_classes = [GeocodeThrottle]
    http_method_names = ["get"]

    def get(self, request: Request) -> Response:
        params: dict[str, object] = dict(request.query_params.items())
        if any(len(request.query_params.getlist(key)) != 1 for key in request.query_params):
            raise APIError("VALIDATION_ERROR", {"query": "DUPLICATE_FIELDS"})
        return Response(
            service_for(request._request).geocode(params, context_for(request._request))
        )


def health(request: HttpRequest) -> JsonResponse:
    """Report process/configuration health without touching providers or databases."""
    if request.method != "GET":
        response = JsonResponse(
            {"error": {"code": "METHOD_NOT_ALLOWED", "message": "Use GET.", "details": {}}},
            status=405,
        )
        response["Allow"] = "GET"
        return response
    readiness = request.GET.get("ready") == "1"
    response = JsonResponse(
        {
            "status": "ready" if readiness else "ok",
            "version": str(settings.APP_VERSION),
            "check": "readiness" if readiness else "liveness",
        }
    )
    response["Cache-Control"] = "no-store"
    return response
