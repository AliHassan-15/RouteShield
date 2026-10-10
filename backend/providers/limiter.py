"""In-process rolling QPS and concurrent-call bounds, shared across adapters."""

from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from threading import BoundedSemaphore, Lock

from providers.deadline import Deadline
from providers.errors import ErrorCode, ProviderError


class ProviderLimiter:
    """Reserve actual call starts; connection pooling is not result caching."""

    def __init__(
        self,
        clock: Callable[[], float],
        sleeper: Callable[[float], None],
        *,
        requests_per_second: int = 5,
        concurrency: int = 2,
    ) -> None:
        if (
            type(requests_per_second) is not int
            or not 1 <= requests_per_second <= 5
            or type(concurrency) is not int
            or not 1 <= concurrency <= 2
        ):
            raise ProviderError(ErrorCode.INVALID_REQUEST)
        self._clock = clock
        self._sleeper = sleeper
        self._limit = requests_per_second
        self._starts: deque[float] = deque()
        self._lock = Lock()
        self._slots = BoundedSemaphore(concurrency)

    @contextmanager
    def slot(self, deadline: Deadline) -> Iterator[None]:
        """Hold concurrency until the transport actually finishes, even on timeout."""
        deadline.check()
        if not self._slots.acquire(timeout=deadline.remaining()):
            raise ProviderError(ErrorCode.PROVIDER_TIMEOUT)
        try:
            while True:
                deadline.check()
                with self._lock:
                    now = self._clock()
                    while self._starts and now - self._starts[0] >= 1:
                        self._starts.popleft()
                    if len(self._starts) < self._limit:
                        self._starts.append(now)
                        break
                    wait = max(0.0, 1 - (now - self._starts[0]))
                deadline.sleep(wait, self._sleeper)
            yield
        finally:
            self._slots.release()
