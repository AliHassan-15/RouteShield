"""Closed public error vocabulary: never serialize exception text or provider bodies."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from providers.errors import ErrorCode, ProviderError

ERRORS: dict[str, tuple[int, str]] = {
    "VALIDATION_ERROR": (400, "Check the highlighted input fields."),
    "PAYLOAD_TOO_LARGE": (413, "The JSON request must be at most 16 KB."),
    "UNSUPPORTED_MEDIA_TYPE": (415, "Use application/json."),
    "LOCATION_REQUIRES_SELECTION": (422, "Select a location with coordinates."),
    "NO_ROUTE": (422, "No route is available for these locations."),
    "TRIP_TOO_LARGE": (422, "Mandatory checkpoints exceed 200 locations at 50-mile spacing."),
    "THROTTLED": (429, "Too many requests; wait before trying again."),
    "DEADLINE_EXCEEDED": (
        504,
        "The analysis exceeded its time budget before routes were available.",
    ),
    "PROVIDER_TIMEOUT": (504, "The provider operation exceeded its time budget."),
    "PROVIDER_UNAVAILABLE": (503, "The provider is temporarily unavailable."),
    "QUOTA_EXCEEDED": (503, "The provider request allowance has been reached."),
    "PROVIDER_AUTH": (502, "The provider credentials are unavailable or not authorized."),
    "MALFORMED_PROVIDER_RESPONSE": (502, "The provider returned invalid or incomplete data."),
    "INTERNAL_ERROR": (500, "The request could not be completed."),
    "METHOD_NOT_ALLOWED": (405, "Use the endpoint's documented HTTP method."),
    "NOT_FOUND": (404, "The API endpoint does not exist."),
    "SIMULATION_DISABLED": (400, "Simulation is not available in this API milestone."),
    "INVALID_SCENARIO": (400, "Choose a documented simulation scenario."),
}


@dataclass
class APIError(Exception):
    code: str
    details: Mapping[str, object] = field(default_factory=dict)
    retry_after: int | None = None
    message: str | None = None

    @property
    def status(self) -> int:
        return ERRORS[self.code][0]

    def envelope(self) -> dict[str, object]:
        return {
            "error": {
                "code": self.code,
                "message": self.message or ERRORS[self.code][1],
                "details": dict(self.details),
            }
        }


def provider_error(error: ProviderError, *, expired: bool = False) -> APIError:
    """The adapter's safe closed code is sufficient; arbitrary upstream details are dropped."""
    if expired:
        return APIError("DEADLINE_EXCEEDED")
    code = "VALIDATION_ERROR" if error.code is ErrorCode.INVALID_REQUEST else error.code.value
    return APIError(code)
