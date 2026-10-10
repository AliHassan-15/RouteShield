"""Independent PDF/D01 boundary oracles and complete load-rule cross products."""

from decimal import Decimal

import pytest
from domain.risk import classify_checkpoint, classify_hazard
from domain.risk_types import Hazard, RiskLevel

L, M, H, S, N = tuple(RiskLevel)

# Expected values are independent of the production policy, so policy typos fail.
BOUNDARIES = [
    (Hazard.WIND, "25", (L, M, M)),
    (Hazard.WIND, "34", (M, M, M)),
    (Hazard.WIND, "35", (M, H, H)),
    (Hazard.WIND, "44", (H, H, H)),
    (Hazard.WIND, "45", (H, S, S)),
    (Hazard.WIND, "54", (S, S, S)),
    (Hazard.WIND, "55", (S, N, N)),
    (Hazard.RAIN, "0.10", (L, M, M)),
    (Hazard.RAIN, "0.25", (M, H, H)),
    (Hazard.RAIN, "0.50", (H, S, S)),
    (Hazard.RAIN, "1.00", (S, S, N)),
    (Hazard.SNOW, "0.5", (L, M, M)),
    (Hazard.SNOW, "1.0", (M, H, H)),
    (Hazard.SNOW, "2.0", (H, S, S)),
    (Hazard.SNOW, "3.0", (S, S, N)),
]


@pytest.mark.parametrize("hazard,boundary,expected", BOUNDARIES)
@pytest.mark.parametrize("offset", [-1, 0, 1], ids=["below", "exact", "above"])
def test_all_printed_endpoints(
    hazard: Hazard, boundary: str, expected: tuple[RiskLevel, ...], offset: int
) -> None:
    """Neighbor generation belongs to tests, never to classification."""
    value = Decimal(boundary) + Decimal("0.0001") * offset
    assert classify_hazard(hazard, value) is expected[offset + 1]


@pytest.mark.parametrize(
    "value,expected",
    [
        ("34.5", M),
        ("34.99", M),
        ("44.5", H),
        ("44.9", H),
        ("54.5", S),
        ("54.99", S),
    ],
)
def test_wind_fractional_gaps(value: str, expected: RiskLevel) -> None:
    """Approved continuous windows cover the PDF's integer gaps."""
    assert classify_hazard(Hazard.WIND, Decimal(value)) is expected


@pytest.mark.parametrize(
    "hazard,value,expected",
    [
        (Hazard.RAIN, "1.00", S),
        (Hazard.RAIN, "1.0001", N),
        (Hazard.SNOW, "3.0", S),
        (Hazard.SNOW, "3.0001", N),
        (Hazard.WIND, "0", L),
        (Hazard.RAIN, "0", L),
        (Hazard.SNOW, "0", L),
    ],
)
def test_strict_cutoffs_and_zero(hazard: Hazard, value: str, expected: RiskLevel) -> None:
    """Precipitation upper endpoints differ from the inclusive wind cutoff."""
    assert classify_hazard(hazard, Decimal(value)) is expected


@pytest.mark.parametrize(
    "weight,expected",
    [
        ("30000", (M, H, H, S, S, N)),
        ("30000.01", (M, H, H, N, N, N)),
        ("30001", (M, H, H, N, N, N)),
        ("40000", (M, H, H, N, N, N)),
        ("40000.01", (M, S, S, N, N, N)),
        ("40001", (M, S, S, N, N, N)),
    ],
)
@pytest.mark.parametrize("index,wind", list(enumerate(["34.9", "35", "44.9", "45", "54.9", "55"])))
def test_user_load_cross_product(
    weight: str, expected: tuple[RiskLevel, ...], index: int, wind: str
) -> None:
    """All six requested decimal weights are crossed with all six wind values."""
    result = classify_checkpoint(
        wind_mph=Decimal(wind),
        rain_in_per_hour=0,
        snow_in_per_hour=0,
        load_weight_lb=Decimal(weight),
    )
    assert result.load_adjusted_wind_level is expected[index]
    assert result.final_level is expected[index]


@pytest.mark.parametrize(
    "wind,expected",
    [
        ("34.9999", (M, M, M, M, M, M, M)),
        ("35", (H, H, H, H, H, H, S)),
        ("44", (H, H, H, H, H, H, S)),
        ("44.5", (H, H, H, H, H, H, S)),
        ("44.9999", (H, H, H, H, H, H, S)),
        ("45", (S, S, S, N, N, N, N)),
        ("54", (S, S, S, N, N, N, N)),
        ("54.5", (S, S, S, N, N, N, N)),
        ("54.9999", (S, S, S, N, N, N, N)),
        ("55", (N, N, N, N, N, N, N)),
        ("55.0001", (N, N, N, N, N, N, N)),
    ],
)
@pytest.mark.parametrize(
    "index,weight",
    list(
        enumerate(
            [
                "0",
                "29999.9999",
                "30000",
                "30000.0001",
                "39999.9999",
                "40000",
                "40000.0001",
            ]
        )
    ),
)
def test_acceptance_load_matrix(
    wind: str, expected: tuple[RiskLevel, ...], index: int, weight: str
) -> None:
    """RISK-04's full 77-case matrix also covers tiny strict-load differences."""
    result = classify_checkpoint(
        wind_mph=Decimal(wind),
        rain_in_per_hour=0,
        snow_in_per_hour=0,
        load_weight_lb=Decimal(weight),
    )
    assert result.load_adjusted_wind_level is expected[index]


def test_extreme_wind_blocks_zero_cargo() -> None:
    """The unconditional wind rule applies even at zero load."""
    result = classify_checkpoint(
        wind_mph=55, rain_in_per_hour=0, snow_in_per_hour=0, load_weight_lb=0
    )
    assert result.hazard_level is N
    assert result.load_adjusted_wind_level is N
    assert result.final_level is N and result.known_blocked
