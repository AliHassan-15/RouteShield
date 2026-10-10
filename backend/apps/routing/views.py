"""Provider-independent health endpoints for the stateless foundation."""

from django.conf import settings
from django.http import HttpRequest, JsonResponse


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
