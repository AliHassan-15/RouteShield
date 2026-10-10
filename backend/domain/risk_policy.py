"""Single risk policy: PDF transcription plus approved D01/D20 conventions.

Source: Requirements/fs-assessment-spotter.pdf; decisions D01/D02/D20.
Printed wind integer ranges are retained verbatim as labels. Their effective
continuous upper limits and shared precipitation endpoints implement D01.
Rain exactly 1.00 and snow exactly 3.0 remain Severe; No Travel is strictly >.
Load windows refer to the classified wind bands, so cutoffs are never copied
into the classifier. Cargo bounds are input guards, not truck weight ratings.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

from domain.risk_types import Hazard, ReasonCode, RiskBand, RiskLevel


@dataclass(frozen=True, slots=True)
class LoadRule:
    """Apply to one wind band; a null cargo threshold means any load."""

    wind_level: RiskLevel
    cargo_threshold_lb: Decimal | None
    resulting_level: RiskLevel
    code: ReasonCode


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    """Deeply immutable thresholds, load rules and normalized-input bounds."""

    hazard_bands: Mapping[Hazard, tuple[RiskBand, ...]]
    load_rules: tuple[LoadRule, ...]
    minimum_value: Decimal
    maximum_cargo_weight_lb: Decimal


# REQUIREMENT: printed labels/load operators. APPROVED: effective D01 intervals,
# D02 ordinals and D20's product envelope. All numeric policy lives here.
RISK_POLICY = RiskPolicy(
    hazard_bands=MappingProxyType(
        {
            Hazard.WIND: (
                RiskBand(RiskLevel.LOW, "<25", upper=Decimal("25")),
                RiskBand(RiskLevel.MODERATE, "25–34", Decimal("25"), Decimal("35")),
                RiskBand(RiskLevel.HIGH, "35–44", Decimal("35"), Decimal("45")),
                RiskBand(RiskLevel.SEVERE, "45–54", Decimal("45"), Decimal("55")),
                RiskBand(RiskLevel.NO_TRAVEL, "≥55", lower=Decimal("55")),
            ),
            Hazard.RAIN: (
                RiskBand(RiskLevel.LOW, "<0.10", upper=Decimal("0.10")),
                RiskBand(RiskLevel.MODERATE, "0.10–0.25", Decimal("0.10"), Decimal("0.25")),
                RiskBand(RiskLevel.HIGH, "0.25–0.50", Decimal("0.25"), Decimal("0.50")),
                RiskBand(
                    RiskLevel.SEVERE,
                    "0.50–1.00",
                    Decimal("0.50"),
                    Decimal("1.00"),
                    upper_inclusive=True,
                ),
                RiskBand(RiskLevel.NO_TRAVEL, ">1.00", Decimal("1.00"), lower_inclusive=False),
            ),
            Hazard.SNOW: (
                RiskBand(RiskLevel.LOW, "<0.5", upper=Decimal("0.5")),
                RiskBand(RiskLevel.MODERATE, "0.5–1.0", Decimal("0.5"), Decimal("1.0")),
                RiskBand(RiskLevel.HIGH, "1.0–2.0", Decimal("1.0"), Decimal("2.0")),
                RiskBand(
                    RiskLevel.SEVERE,
                    "2.0–3.0",
                    Decimal("2.0"),
                    Decimal("3.0"),
                    upper_inclusive=True,
                ),
                RiskBand(RiskLevel.NO_TRAVEL, ">3.0", Decimal("3.0"), lower_inclusive=False),
            ),
        }
    ),
    load_rules=(
        LoadRule(RiskLevel.NO_TRAVEL, None, RiskLevel.NO_TRAVEL, ReasonCode.EXTREME_WIND_ANY_LOAD),
        LoadRule(
            RiskLevel.SEVERE,
            Decimal("30000"),
            RiskLevel.NO_TRAVEL,
            ReasonCode.SEVERE_WIND_HEAVY_LOAD,
        ),
        LoadRule(
            RiskLevel.HIGH,
            Decimal("40000"),
            RiskLevel.SEVERE,
            ReasonCode.HIGH_WIND_HEAVY_LOAD,
        ),
    ),
    minimum_value=Decimal("0"),
    maximum_cargo_weight_lb=Decimal("100000"),
)
