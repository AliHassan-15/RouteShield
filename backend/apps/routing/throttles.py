"""Settings-driven DRF throttles with explicit trusted-proxy handling."""

import hashlib
import ipaddress
from threading import Lock
from typing import TYPE_CHECKING, cast

from django.conf import settings
from rest_framework.request import Request  # type: ignore[import-untyped]
from rest_framework.throttling import SimpleRateThrottle  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from rest_framework.views import APIView  # type: ignore[import-untyped]

_LOCK = Lock()


def client_ip(request: Request) -> str:
    """Ignore forwarded headers unless the immediate peer belongs to configured CIDRs."""
    try:
        peer = ipaddress.ip_address(request.META.get("REMOTE_ADDR", "127.0.0.1"))
        trusted = tuple(ipaddress.ip_network(cidr) for cidr in settings.API_TRUSTED_PROXY_CIDRS)
        if not any(peer in network for network in trusted):
            return str(peer)
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if len(forwarded) > 2048:
            return str(peer)
        addresses = [
            ipaddress.ip_address(part.strip()) for part in forwarded.split(",") if part.strip()
        ]
        for address in reversed(addresses):
            if not any(address in network for network in trusted):
                return str(address)
        return str(addresses[0]) if addresses else str(peer)
    except ValueError:
        return str(request.META.get("REMOTE_ADDR", "127.0.0.1"))


class EndpointThrottle(SimpleRateThrottle):  # type: ignore[misc]
    scope = "analysis"

    def get_rate(self) -> str:
        prefix = "ANALYSIS" if self.scope == "analysis" else "GEOCODE"
        self.limit = int(getattr(settings, prefix + "_RATE_LIMIT"))
        self.window = int(getattr(settings, prefix + "_RATE_WINDOW_SECONDS"))
        return str(self.limit)

    def parse_rate(self, rate: str | None) -> tuple[int, int]:
        return self.limit, self.window

    def get_cache_key(self, request: Request, view: "APIView") -> str:
        identifier = hashlib.sha256(client_ip(request).encode()).hexdigest()
        return f"api-throttle:{self.scope}:{identifier}"

    def allow_request(self, request: Request, view: "APIView") -> bool:
        # LocMemCache operations alone are not atomic read-modify-write transactions.
        with _LOCK:
            return cast(bool, super().allow_request(request, view))


class AnalysisThrottle(EndpointThrottle):
    scope = "analysis"


class GeocodeThrottle(EndpointThrottle):
    scope = "geocode"
