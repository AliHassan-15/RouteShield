"""Synthetic, injected transport and time; no raw recordings or network."""

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from domain.geometry import geometric_chainage
from domain.route_types import Coordinate
from providers.deadline import Deadline
from providers.limiter import ProviderLimiter
from providers.transport import (
    DEFAULT_TRANSPORT_CONFIG,
    HTTPResponse,
    TomTomTransport,
    TransportConfig,
)

FAKE_KEY = "synthetic-provider-key-for-tests"
NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)
FIXTURES = Path(__file__).parent / "fixtures" / "providers"


class FakeTime:
    def __init__(self) -> None:
        self.seconds = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.seconds

    def utc(self) -> datetime:
        return NOW + timedelta(seconds=self.seconds)

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.seconds += seconds

    def deadline(self, seconds: float = 35) -> Deadline:
        return Deadline(seconds, self.monotonic)


class FakeClient:
    def __init__(self, responses: Sequence[HTTPResponse | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, tuple[tuple[str, str], ...], httpx.Timeout]] = []

    def get(
        self,
        url: str,
        *,
        params: Sequence[tuple[str, str]],
        timeout: httpx.Timeout,
        deadline: Deadline,
    ) -> HTTPResponse:
        self.calls.append((url, tuple(params), timeout))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def transport(
    client: FakeClient, time: FakeTime, config: TransportConfig = DEFAULT_TRANSPORT_CONFIG
) -> TomTomTransport:
    return TomTomTransport(
        client, FAKE_KEY, ProviderLimiter(time.monotonic, time.sleep), time.utc, time.sleep, config
    )


def response(
    body: object,
    status: int = 200,
    *,
    content_type: str = "application/json",
    retry_after: str | None = None,
) -> HTTPResponse:
    return HTTPResponse(status, json.dumps(body).encode(), content_type, retry_after)


def fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def route_payload(points: Sequence[Coordinate], duration: int = 600) -> dict[str, object]:
    """Invent geometry, derive consistent meters and provide actual sparse anchors."""
    chain = geometric_chainage(points)
    length = round(chain[-1])
    middle = len(points) // 2
    indices = sorted({0, middle, len(points) - 1})
    anchors = [
        {
            "pointIndex": i,
            "distanceInMeters": float(chain[i] / chain[-1] * length),
            "travelTimeInSeconds": 0
            if i == 0
            else duration
            if i == len(points) - 1
            else duration // 4,
        }
        for i in indices
    ]
    return {
        "summary": {"lengthInMeters": length, "travelTimeInSeconds": duration},
        "legs": [{"points": [{"latitude": p.latitude, "longitude": p.longitude} for p in points]}],
        "progress": anchors,
    }


def normalized_payload(points: Sequence[Coordinate], duration: int = 600) -> dict[str, object]:
    return {
        "routes": [route_payload(points, duration)],
        "_fixture": {"provenance": "SYNTHETIC", "live_result": False},
    }


ORIGIN = Coordinate(-100, 34)
DESTINATION = Coordinate(-99.98, 34.02)
SPARSE_POINTS = (
    ORIGIN,
    Coordinate(-99.995, 34.004),
    Coordinate(-99.99, 34.006),
    Coordinate(-99.985, 34.015),
    DESTINATION,
)
