"""Explicit presentation shapes; ranking and classification remain in the domain."""

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from fractions import Fraction
from math import isfinite

from domain.risk_types import CheckpointRisk, RiskLevel
from domain.route_types import Coordinate


def utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def epoch_text(value: Fraction | int) -> str:
    """ISO display timestamps use datetime's explicit microsecond resolution."""
    return utc_text(
        datetime(1970, 1, 1, tzinfo=UTC) + timedelta(microseconds=round(value * 1_000_000))
    )


def public(value: object) -> object:
    """Fractions are lossless integer ratios; decimals are exact strings, enums names."""
    if isinstance(value, Enum):
        return value.name if isinstance(value, RiskLevel) else value.value
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Fraction):
        return {"numerator": str(value.numerator), "denominator": str(value.denominator)}
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Unsafe numeric output")
        return str(value)
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("Unsafe numeric output")
        return value
    if isinstance(value, datetime):
        return utc_text(value)
    if isinstance(value, Coordinate):
        return [value.longitude, value.latitude]
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: public(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {str(public(k)): public(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [public(v) for v in value]
    raise TypeError("Unsupported public value")


def risk_result(risk: CheckpointRisk) -> dict[str, object]:
    return {
        "wind_risk": public(risk.wind_level),
        "rain_risk": public(risk.rain_level),
        "snow_risk": public(risk.snow_level),
        "hazard_risk": public(risk.hazard_level),
        "load_adjusted_wind_risk": public(risk.load_adjusted_wind_level),
        "final_risk": public(risk.final_level),
        "known_risk_floor": public(risk.known_risk_floor),
        "known_blocked": risk.known_blocked,
        "ordinal": risk.final_level.value if isinstance(risk.final_level, RiskLevel) else None,
        "reasons": public(risk.reasons),
    }
