"""Exact conservative published Open-Meteo accounting and atomic process ledger."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from fractions import Fraction
from threading import Lock

from providers.contracts import WeatherWindow
from providers.errors import ErrorCode, ProviderError
from providers.forecast import validate_window


def quota_units(
    coordinates: int, variables: int, window: WeatherWindow, models: int = 1
) -> Fraction:
    """C × max(1,V/10) × max(1,inclusive UTC calendar days/14) × requested models.

    Fractional charging is conservatively modeled from the published calculator;
    automatic best-match counts as one requested selection, not guessed internals.
    """
    validate_window(window)
    if any(type(n) is not int or n < 1 for n in (coordinates, variables, models)):
        raise ProviderError(ErrorCode.INVALID_REQUEST)
    first = datetime.fromtimestamp(window.start_epoch, UTC).date()
    last = datetime.fromtimestamp(window.end_epoch, UTC).date()
    days = (last - first).days + 1
    return (
        coordinates
        * max(Fraction(1), Fraction(variables, 10))
        * max(Fraction(1), Fraction(days, 14))
        * models
    )


@dataclass(slots=True)
class Reservation:
    day: date
    units: Fraction
    sent: bool = False
    released: bool = False


class QuotaLedger:
    """In-process UTC-day reservations; resets on restart, no distributed guarantee."""

    def __init__(
        self, clock: Callable[[], datetime], *, daily_limit: int = 8000, request_limit: int = 200
    ) -> None:
        if any(type(n) is not int or n <= 0 for n in (daily_limit, request_limit)):
            raise ProviderError(ErrorCode.INVALID_REQUEST)
        self._clock, self.daily_limit, self.request_limit = clock, daily_limit, request_limit
        self._day = clock().astimezone(UTC).date()
        self._used = Fraction(0)
        self._lock = Lock()

    def _rollover(self) -> None:
        day = self._clock().astimezone(UTC).date()
        if day != self._day:
            self._day, self._used = day, Fraction(0)

    @property
    def used(self) -> Fraction:
        with self._lock:
            self._rollover()
            return self._used

    def reserve(self, units: Fraction) -> Reservation | None:
        """Equality is permitted; reserve before send so concurrent calls cannot overrun."""
        if not isinstance(units, Fraction) or units <= 0:
            raise ProviderError(ErrorCode.INVALID_REQUEST)
        with self._lock:
            self._rollover()
            if units > self.request_limit or self._used + units > self.daily_limit:
                return None
            self._used += units
            return Reservation(self._day, units)

    def mark_sent(self, reservation: Reservation) -> bool:
        """Once HTTP invocation begins, retain cost even on failure (counter unverified)."""
        with self._lock:
            self._rollover()
            if reservation.released:
                return False
            if reservation.sent:
                return True
            if reservation.day != self._day and not reservation.released:
                # A queued reservation crossed midnight: charge the actual send day.
                if self._used + reservation.units > self.daily_limit:
                    reservation.released = True
                    return False
                reservation.day = self._day
                self._used += reservation.units
            reservation.sent = True
            return True

    def release_before_send(self, reservation: Reservation) -> None:
        """Idempotent; a previous-day release never subtracts today's reservations."""
        with self._lock:
            self._rollover()
            if not reservation.sent and not reservation.released:
                if reservation.day == self._day:
                    self._used -= reservation.units
                reservation.released = True
