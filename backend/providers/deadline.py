"""One injectable monotonic deadline, shared by every attempt and fallback."""

from collections.abc import Callable
from fractions import Fraction
from math import isfinite
from threading import Event, Lock

from providers.errors import ErrorCode, ProviderError


class Deadline:
    """A cancelled or exhausted deadline never becomes usable again."""

    def __init__(self, seconds: float, clock: Callable[[], float]) -> None:
        if isinstance(seconds, bool) or not isfinite(seconds) or not 0 < seconds <= 35:
            raise ProviderError(ErrorCode.INVALID_REQUEST)
        self._clock = clock
        self._ends_at = clock() + seconds
        self._cancelled = Event()
        self._metrics_lock = Lock()
        self._calls = {"routing": 0, "geocoding": 0, "weather": 0}
        self._quota_reserved = Fraction(0)

    def record_call(self, provider: str) -> None:
        """Count actual sends per request, including retries, without retaining locations."""
        with self._metrics_lock:
            self._calls[provider] += 1

    def record_reservation(self, units: Fraction) -> None:
        """Count successful reservation attempts (including later pre-send refunds)."""
        with self._metrics_lock:
            self._quota_reserved += units

    def metrics(self) -> tuple[dict[str, int], Fraction]:
        """Snapshot isolated request counters, safely across transport workers."""
        with self._metrics_lock:
            return dict(self._calls), self._quota_reserved

    def remaining(self) -> float:
        """Return remaining seconds without resetting the original budget."""
        return 0.0 if self._cancelled.is_set() else max(0.0, self._ends_at - self._clock())

    def check(self) -> None:
        """Prevent work or successful results after the shared deadline."""
        if self.remaining() <= 0:
            raise ProviderError(ErrorCode.PROVIDER_TIMEOUT)

    def cancel(self) -> None:
        """Stop queued/cooperative work when the caller's hard wait expires."""
        self._cancelled.set()

    def sleep(self, seconds: float, sleeper: Callable[[float], None]) -> None:
        """Backoff/limiter waits count against the same deadline."""
        self.check()
        if seconds < 0 or not isfinite(seconds) or seconds >= self.remaining():
            raise ProviderError(ErrorCode.PROVIDER_TIMEOUT)
        sleeper(seconds)
        self.check()
