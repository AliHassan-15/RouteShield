"""Pure classification of already normalized mph, in/hr and cargo pounds.

Decimal inputs are preserved exactly; integers convert exactly. Floats use
Decimal(str(value)), preserving their shortest round-trip decimal representation,
not rounding to a chosen precision. No epsilon or quantization is applied.
An upstream binary sum already below/above a boundary stays there: its intended
decimal sum cannot be reconstructed. Adapters should parse source decimals and
combine/normalize with adequate Decimal precision before calling this module.
Classification performs comparisons only and is independent of Decimal context.
"""

from collections.abc import Iterable
from decimal import Decimal

from domain.risk_policy import RISK_POLICY
from domain.risk_types import (
    UNKNOWN,
    CheckpointRisk,
    Comparison,
    DomainValidationError,
    Hazard,
    NormalizedNumber,
    ReasonCode,
    Risk,
    RiskBand,
    RiskLevel,
    RiskReason,
    ValidationCode,
)


def _validate(value: NormalizedNumber | None, field: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, float)):
        raise DomainValidationError(
            field,
            ValidationCode.INVALID_NUMBER_TYPE,
            "must be a Decimal, int or float, not a boolean",
        )
    number = Decimal(str(value)) if isinstance(value, float) else Decimal(value)
    if not number.is_finite():
        raise DomainValidationError(field, ValidationCode.NON_FINITE_VALUE, "must be finite")
    if number < RISK_POLICY.minimum_value:
        raise DomainValidationError(field, ValidationCode.NEGATIVE_VALUE, "must be nonnegative")
    if field == "load_weight_lb" and number > RISK_POLICY.maximum_cargo_weight_lb:
        raise DomainValidationError(
            field,
            ValidationCode.LOAD_WEIGHT_OUT_OF_RANGE,
            f"must be at most {RISK_POLICY.maximum_cargo_weight_lb} lb",
        )
    return number


def _band(hazard: Hazard, value: Decimal) -> RiskBand:
    return next(band for band in RISK_POLICY.hazard_bands[hazard] if band.contains(value))


def classify_hazard(hazard: Hazard, value: NormalizedNumber | None) -> Risk:
    """Classify a required normalized hazard; None is unavailable, not Low."""
    number = _validate(value, hazard.value)
    return UNKNOWN if number is None else _band(hazard, number).level


def classify_wind(wind_mph: NormalizedNumber | None) -> Risk:
    """Classify non-gust wind; no unit conversion or load adjustment."""
    return classify_hazard(Hazard.WIND, wind_mph)


def classify_rain(rain_in_per_hour: NormalizedNumber | None) -> Risk:
    """Classify liquid rain already combined with showers by an adapter."""
    return classify_hazard(Hazard.RAIN, rain_in_per_hour)


def classify_snow(snow_in_per_hour: NormalizedNumber | None) -> Risk:
    """Classify snow depth per hour, never its water equivalent."""
    return classify_hazard(Hazard.SNOW, snow_in_per_hour)


def _hazard_reason(hazard: Hazard, value: Decimal | None) -> RiskReason:
    if value is None:
        return RiskReason(ReasonCode.MISSING_HAZARD, hazard.value, None, None, None, None, UNKNOWN)
    band = _band(hazard, value)
    threshold = band.lower if band.lower is not None else band.upper
    comparison = (
        (Comparison.GE if band.lower_inclusive else Comparison.GT)
        if band.lower is not None
        else (Comparison.LE if band.upper_inclusive else Comparison.LT)
    )
    return RiskReason(
        ReasonCode.HAZARD_CLASSIFIED, hazard.value, value, band, threshold, comparison, band.level
    )


def _adjust_wind(
    wind: Decimal | None, weight: Decimal | None, reason: RiskReason
) -> tuple[Risk, tuple[RiskReason, ...]]:
    if wind is None:
        return UNKNOWN, (
            RiskReason(
                ReasonCode.LOAD_RULES_UNAVAILABLE_MISSING_WIND,
                Hazard.WIND.value,
                None,
                None,
                None,
                None,
                UNKNOWN,
                load_weight_lb=weight,
            ),
        )
    for rule in RISK_POLICY.load_rules:
        if reason.level is not rule.wind_level:
            continue
        if rule.cargo_threshold_lb is None or (
            weight is not None and weight > rule.cargo_threshold_lb
        ):
            return rule.resulting_level, (
                RiskReason(
                    rule.code,
                    "load_weight_lb" if rule.cargo_threshold_lb is not None else Hazard.WIND.value,
                    weight if rule.cargo_threshold_lb is not None else wind,
                    reason.band,
                    rule.cargo_threshold_lb
                    if rule.cargo_threshold_lb is not None
                    else reason.threshold,
                    Comparison.GT if rule.cargo_threshold_lb is not None else reason.comparison,
                    rule.resulting_level,
                    wind_mph=wind,
                    load_weight_lb=weight,
                ),
            )
    if weight is None:
        return UNKNOWN, (
            RiskReason(
                ReasonCode.LOAD_RULES_UNAVAILABLE_MISSING_LOAD,
                "load_weight_lb",
                None,
                reason.band,
                None,
                None,
                UNKNOWN,
                wind_mph=wind,
            ),
        )
    return reason.level, ()


def _known_maximum(levels: Iterable[Risk]) -> RiskLevel | None:
    return max((level for level in levels if isinstance(level, RiskLevel)), default=None)


def classify_checkpoint(
    *,
    wind_mph: NormalizedNumber | None,
    rain_in_per_hour: NormalizedNumber | None,
    snow_in_per_hour: NormalizedNumber | None,
    load_weight_lb: NormalizedNumber | None,
) -> CheckpointRisk:
    """Retain all evidence and known blocks even when the final level is UNKNOWN.

    Missing cargo is also an incomplete input, never an implicit zero-load choice.
    Extreme wind can still prove No Travel independently of the missing cargo.
    """
    weight = _validate(load_weight_lb, "load_weight_lb")
    wind = _validate(wind_mph, Hazard.WIND.value)
    rain = _validate(rain_in_per_hour, Hazard.RAIN.value)
    snow = _validate(snow_in_per_hour, Hazard.SNOW.value)
    reasons = tuple(
        _hazard_reason(h, v)
        for h, v in (
            (Hazard.WIND, wind),
            (Hazard.RAIN, rain),
            (Hazard.SNOW, snow),
        )
    )
    adjusted, load_reasons = _adjust_wind(wind, weight, reasons[0])
    wind_level, rain_level, snow_level = (reason.level for reason in reasons)
    known_hazard = _known_maximum((wind_level, rain_level, snow_level))
    hazard = UNKNOWN if None in (wind, rain, snow) else known_hazard
    floor = _known_maximum((wind_level, rain_level, snow_level, adjusted))
    final = UNKNOWN if weight is None or hazard is UNKNOWN else floor
    # A complete validated input always has three known hazard levels and a floor.
    assert hazard is not None and final is not None
    if weight is None:
        load_reasons += (
            RiskReason(
                ReasonCode.MISSING_LOAD,
                "load_weight_lb",
                None,
                None,
                None,
                None,
                UNKNOWN,
            ),
        )
    return CheckpointRisk(
        wind_level,
        rain_level,
        snow_level,
        hazard,
        adjusted,
        final,
        floor,
        floor is RiskLevel.NO_TRAVEL,
        reasons + load_reasons,
    )
