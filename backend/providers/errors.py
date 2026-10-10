"""Closed, credential-free adapter failures; HTTP mapping belongs to the API."""

from enum import StrEnum
from types import MappingProxyType


class ErrorCode(StrEnum):
    NO_ROUTE = "NO_ROUTE"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    PROVIDER_AUTH = "PROVIDER_AUTH"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    MALFORMED_PROVIDER_RESPONSE = "MALFORMED_PROVIDER_RESPONSE"
    INVALID_REQUEST = "INVALID_REQUEST"


ERROR_MESSAGES = MappingProxyType(
    {
        ErrorCode.NO_ROUTE: "No route is available for these locations.",
        ErrorCode.QUOTA_EXCEEDED: "The provider request allowance has been reached.",
        ErrorCode.PROVIDER_AUTH: "The provider credentials are unavailable or not authorized.",
        ErrorCode.PROVIDER_TIMEOUT: "The provider operation exceeded its time budget.",
        ErrorCode.PROVIDER_UNAVAILABLE: "The provider is temporarily unavailable.",
        ErrorCode.MALFORMED_PROVIDER_RESPONSE: "The provider returned invalid or incomplete data.",
        ErrorCode.INVALID_REQUEST: "The provider request is invalid.",
    }
)


class ProviderError(Exception):
    """Never retain upstream exception text, responses, requests or credentials."""

    def __init__(self, code: ErrorCode, *, past_departure_rejected: bool = False) -> None:
        self.code = code
        self.past_departure_rejected = past_departure_rejected
        super().__init__(ERROR_MESSAGES[code])

    def as_dict(self) -> dict[str, object]:
        """Expose only approved safe fields for later public-envelope serialization."""
        return {
            "code": self.code.value,
            "message": str(self),
            "details": {"past_departure_rejected": self.past_departure_rejected},
        }
