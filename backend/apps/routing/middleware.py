"""Bound JSON before parsing; record one location-free request log and correlation header."""

import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from django.http import HttpRequest, HttpResponse, JsonResponse
from providers.deadline import Deadline

from apps.routing import factory
from apps.routing.errors import APIError
from apps.routing.service import AnalysisService, RequestContext
from apps.routing.validation import MAX_BODY_BYTES, SCENARIOS

LOGGER = logging.getLogger("routeshield.requests")
ENDPOINT_NAMES = {
    "/api/v1/route-analysis/": "route_analysis",
    "/api/v1/geocode/": "geocode",
    "/api/v1/health/": "health",
}


def context_for(request: HttpRequest) -> RequestContext:
    return cast(RequestContext, request.__dict__["api_context"])


def service_for(request: HttpRequest) -> AnalysisService:
    return cast(AnalysisService, request.__dict__["api_service"])


def error_response(error: APIError, request: HttpRequest) -> JsonResponse:
    payload = error.envelope()
    if request.path == "/api/v1/route-analysis/":
        payload.update(
            {
                "is_simulation": getattr(request, "api_simulated", False),
                "simulation_scenario": getattr(request, "api_scenario", None),
            }
        )
    response = JsonResponse(payload, status=error.status)
    if error.retry_after is not None:
        response["Retry-After"] = str(error.retry_after)
    return response


class APIRequestMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not request.path.startswith("/api/"):
            return self.get_response(request)
        service: AnalysisService | None = None
        start = time.monotonic()
        context: RequestContext | None = None
        try:
            if request.path in ("/api/v1/route-analysis/", "/api/v1/geocode/"):
                service = factory.get_service()
                context = service.begin()
                request.__dict__["api_service"] = service
            else:
                context = RequestContext(
                    str(uuid4()), start, datetime.now(UTC), Deadline(35, time.monotonic), 35
                )
            request.__dict__["api_context"] = context
            if request.path == "/api/v1/route-analysis/" and request.method == "POST":
                if request.content_type != "application/json":
                    raise APIError("UNSUPPORTED_MEDIA_TYPE")
                length = request.META.get("CONTENT_LENGTH", "")
                try:
                    if length and int(length) > MAX_BODY_BYTES:
                        raise APIError("PAYLOAD_TOO_LARGE")
                    if length and int(length) < 0:
                        raise ValueError("negative length")
                except ValueError:
                    raise APIError("VALIDATION_ERROR", {"body": "INVALID_CONTENT_LENGTH"}) from None
                raw = request.read(MAX_BODY_BYTES + 1)
                if len(raw) > MAX_BODY_BYTES:
                    raise APIError("PAYLOAD_TOO_LARGE")
                request.__dict__["api_body"] = raw
            response = self.get_response(request)
            if response.status_code == 404:
                response = error_response(APIError("NOT_FOUND"), request)
            elif response.status_code >= 400 and not response.get("Content-Type", "").startswith(
                "application/json"
            ):
                response = error_response(APIError("INTERNAL_ERROR"), request)
        except APIError as error:
            response = error_response(error, request)
        except Exception:
            response = error_response(APIError("INTERNAL_ERROR"), request)
        if context is None:
            context = RequestContext(
                str(uuid4()), start, datetime.now(UTC), Deadline(35, time.monotonic), 35
            )
        response["X-Request-ID"] = context.request_id
        response["Cache-Control"] = "no-store"
        counts, _ = context.deadline.metrics()
        total = (
            service.metadata(context)["total_ms"] if service else (time.monotonic() - start) * 1000
        )
        LOGGER.info(
            json.dumps(
                {
                    "request_id": context.request_id,
                    "route_name": ENDPOINT_NAMES.get(request.path, "unknown_api"),
                    "status": response.status_code,
                    "total_ms": total,
                    "stage_ms": context.stages,
                    "provider_calls": counts,
                },
                allow_nan=False,
            )
        )
        return response


def record_simulation_attempt(request: HttpRequest, value: object) -> None:
    """Only bounded documented IDs may appear in an error; never echo arbitrary input."""
    if isinstance(value, dict):
        scenario = value.get("simulation_scenario")
        if scenario is not None:
            request.__dict__["api_simulated"] = True
            request.__dict__["api_scenario"] = scenario if scenario in SCENARIOS else None
