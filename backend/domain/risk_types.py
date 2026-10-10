"""Immutable risk values and explanations; UNKNOWN has no numeric severity."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, IntEnum, StrEnum

type NormalizedNumber = Decimal | int | float


class RiskLevel(IntEnum):
    """D02's totally ordered severity scale, not a probability."""

    LOW = 1
    MODERATE = 2
    HIGH = 3
    SEVERE = 4
    NO_TRAVEL = 5

    @property
    def ordinal(self) -> int:
        """Return the approved ordinal for complete numeric classification."""
        return self.value


class UnknownRisk(Enum):
    """An unavailable assessment cannot participate in ordinal comparisons."""

    UNKNOWN = "UNKNOWN"

    @property
    def ordinal(self) -> None:
        """Missing evidence is never assigned zero or a severity ordinal."""
        return None


UNKNOWN = UnknownRisk.UNKNOWN
type Risk = RiskLevel | UnknownRisk


class Hazard(StrEnum):
    """Required normalized observations; rain already includes showers."""

    WIND = "wind_mph"
    RAIN = "rain_in_per_hour"
    SNOW = "snow_in_per_hour"


class ReasonCode(StrEnum):
    """Stable explanation codes for presentation without frontend risk rules."""

    HAZARD_CLASSIFIED = "HAZARD_CLASSIFIED"
    MISSING_HAZARD = "MISSING_HAZARD"
    EXTREME_WIND_ANY_LOAD = "EXTREME_WIND_ANY_LOAD"
    SEVERE_WIND_HEAVY_LOAD = "SEVERE_WIND_HEAVY_LOAD"
    HIGH_WIND_HEAVY_LOAD = "HIGH_WIND_HEAVY_LOAD"
    LOAD_RULES_UNAVAILABLE_MISSING_WIND = "LOAD_RULES_UNAVAILABLE_MISSING_WIND"
    LOAD_RULES_UNAVAILABLE_MISSING_LOAD = "LOAD_RULES_UNAVAILABLE_MISSING_LOAD"
    MISSING_LOAD = "MISSING_LOAD"


class Comparison(StrEnum):
    """The operator connecting a measured value to an explanation threshold."""

    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="


class ValidationCode(StrEnum):
    """Safe machine-readable domain validation failures."""

    INVALID_NUMBER_TYPE = "INVALID_NUMBER_TYPE"
    NON_FINITE_VALUE = "NON_FINITE_VALUE"
    NEGATIVE_VALUE = "NEGATIVE_VALUE"
    LOAD_WEIGHT_OUT_OF_RANGE = "LOAD_WEIGHT_OUT_OF_RANGE"


class DomainValidationError(ValueError):
    """Identify the invalid field without exposing arbitrary input contents."""

    def __init__(self, field: str, code: ValidationCode, message: str) -> None:
        self.field = field
        self.code = code
        super().__init__(f"{field}: {message}")


@dataclass(frozen=True, slots=True)
class RiskBand:
    """The PDF label alongside its approved D01 continuous interval."""

    level: RiskLevel
    printed_pdf_band: str
    lower: Decimal | None = None
    upper: Decimal | None = None
    lower_inclusive: bool = True
    upper_inclusive: bool = False

    def contains(self, value: Decimal) -> bool:
        """Test endpoints without rounding, epsilon adjustments or arithmetic."""
        if self.lower is not None:
            if value < self.lower or (value == self.lower and not self.lower_inclusive):
                return False
        if self.upper is not None:
            if value > self.upper or (value == self.upper and not self.upper_inclusive):
                return False
        return True


@dataclass(frozen=True, slots=True)
class RiskReason:
    """A measured condition, effective wind/hazard band and comparison evidence."""

    code: ReasonCode
    metric: str
    measured_value: Decimal | None
    band: RiskBand | None
    threshold: Decimal | None
    comparison: Comparison | None
    level: Risk
    wind_mph: Decimal | None = None
    load_weight_lb: Decimal | None = None


@dataclass(frozen=True, slots=True)
class CheckpointRisk:
    """D02/D08 layers; known evidence survives an incomplete final assessment."""

    wind_level: Risk
    rain_level: Risk
    snow_level: Risk
    hazard_level: Risk
    load_adjusted_wind_level: Risk
    final_level: Risk
    known_risk_floor: RiskLevel | None
    known_blocked: bool
    reasons: tuple[RiskReason, ...]
