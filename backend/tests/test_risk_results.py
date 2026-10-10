"""Risk layers, structured explanations, partial evidence and immutability."""

import operator
from collections.abc import MutableMapping
from dataclasses import FrozenInstanceError
from decimal import Decimal
from typing import cast

import pytest
from domain.risk import classify_checkpoint, classify_rain, classify_snow, classify_wind
from domain.risk_policy import RISK_POLICY
from domain.risk_types import UNKNOWN, Comparison, Hazard, ReasonCode, RiskBand, RiskLevel

L, M, H, S, N = tuple(RiskLevel)


def test_known_scale_and_unknown_are_separate() -> None:
    """Only known risks have ordinals and participate in the total order."""
    assert [level.ordinal for level in RiskLevel] == [1, 2, 3, 4, 5]
    assert L < M < H < S < N
    assert sorted(reversed(tuple(RiskLevel))) == list(RiskLevel)
    assert UNKNOWN.ordinal is None
    assert not isinstance(UNKNOWN.value, int)
    # Deliberately exercise invalid runtime operations as well as the static type guard.
    with pytest.raises(TypeError):
        operator.lt(UNKNOWN, L)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        operator.gt(UNKNOWN, N)  # type: ignore[arg-type]


@pytest.mark.parametrize("wind,wind_level", [(10, L), (30, M), (40, H), (50, S), (55, N)])
@pytest.mark.parametrize(
    "rain,rain_level", [("0", L), (".1", M), (".25", H), (".5", S), ("1.0001", N)]
)
@pytest.mark.parametrize(
    "snow,snow_level", [("0", L), (".5", M), ("1", H), ("2", S), ("3.0001", N)]
)
def test_all_hazard_combinations(
    wind: int,
    wind_level: RiskLevel,
    rain: str,
    rain_level: RiskLevel,
    snow: str,
    snow_level: RiskLevel,
) -> None:
    """All 125 hazard combinations use maximum severity, never a compound sum."""
    result = classify_checkpoint(
        wind_mph=wind,
        rain_in_per_hour=Decimal(rain),
        snow_in_per_hour=Decimal(snow),
        load_weight_lb=0,
    )
    expected = max(wind_level, rain_level, snow_level)
    assert (result.wind_level, result.rain_level, result.snow_level) == (
        wind_level,
        rain_level,
        snow_level,
    )
    assert result.hazard_level is expected
    assert result.load_adjusted_wind_level is wind_level
    assert result.final_level is expected and result.known_risk_floor is expected
    assert result.known_blocked is (expected is N)


@pytest.mark.parametrize(
    "missing,floor",
    [
        ((True, False, False), N),
        ((False, True, False), N),
        ((False, False, True), N),
        ((True, True, False), H),
        ((True, False, True), N),
        ((False, True, True), N),
        ((True, True, True), None),
    ],
)
def test_every_missing_hazard_subset_preserves_proven_evidence(
    missing: tuple[bool, bool, bool], floor: RiskLevel | None
) -> None:
    """Known rain and load blocks survive; an entirely missing observation has no floor."""
    wind, rain, snow = (
        None if missing[i] else value
        for i, value in enumerate((Decimal("50"), Decimal("1.0001"), Decimal("1")))
    )
    result = classify_checkpoint(
        wind_mph=wind,
        rain_in_per_hour=rain,
        snow_in_per_hour=snow,
        load_weight_lb=30001,
    )
    assert result.final_level is UNKNOWN and result.hazard_level is UNKNOWN
    assert result.final_level.ordinal is None
    assert result.known_risk_floor is floor
    assert result.known_blocked is (floor is N)
    assert (result.wind_level, result.rain_level, result.snow_level) == tuple(
        UNKNOWN if absent else level for absent, level in zip(missing, (S, N, H), strict=True)
    )
    assert result.load_adjusted_wind_level is (UNKNOWN if missing[0] else N)
    codes = [reason.code for reason in result.reasons]
    assert codes.count(ReasonCode.MISSING_HAZARD) == sum(missing)
    assert (ReasonCode.LOAD_RULES_UNAVAILABLE_MISSING_WIND in codes) is missing[0]


@pytest.mark.parametrize(
    "missing",
    [
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, True, False),
        (True, False, True),
        (False, True, True),
        (True, True, True),
    ],
)
def test_unknown_never_becomes_low(missing: tuple[bool, bool, bool]) -> None:
    """Zero known hazards may prove only a floor, never a complete safe assessment."""
    result = classify_checkpoint(
        wind_mph=None if missing[0] else 0,
        rain_in_per_hour=None if missing[1] else 0,
        snow_in_per_hour=None if missing[2] else 0,
        load_weight_lb=0,
    )
    assert result.final_level is UNKNOWN and not result.known_blocked
    assert result.known_risk_floor is (None if all(missing) else L)


@pytest.mark.parametrize(
    "wind,rain,snow,weight,floor",
    [
        ("55", None, "0", "0", N),
        ("45", None, "0", "30000.01", N),
        ("35", "0", None, "40000.01", S),
        (None, None, "3.0001", "0", N),
    ],
)
def test_explicit_unknown_block_and_load_examples(
    wind: str | None, rain: str | None, snow: str | None, weight: str, floor: RiskLevel
) -> None:
    """D08 retains a hazard/load floor rather than guessing missing measurements."""
    result = classify_checkpoint(
        wind_mph=None if wind is None else Decimal(wind),
        rain_in_per_hour=None if rain is None else Decimal(rain),
        snow_in_per_hour=None if snow is None else Decimal(snow),
        load_weight_lb=Decimal(weight),
    )
    assert result.final_level is UNKNOWN
    assert result.known_risk_floor is floor and result.known_blocked is (floor is N)


@pytest.mark.parametrize(
    "wind,expected_hazard,floor", [(0, L, L), (35, H, H), (45, S, S), (55, N, N)]
)
def test_missing_cargo_is_not_zero(wind: int, expected_hazard: RiskLevel, floor: RiskLevel) -> None:
    """Missing cargo is incomplete, but extreme wind still proves an unconditional block."""
    result = classify_checkpoint(
        wind_mph=wind, rain_in_per_hour=0, snow_in_per_hour=0, load_weight_lb=None
    )
    assert result.hazard_level is expected_hazard and result.final_level is UNKNOWN
    assert result.known_risk_floor is floor and result.known_blocked is (floor is N)
    assert result.load_adjusted_wind_level is (N if wind == 55 else UNKNOWN)
    assert ReasonCode.MISSING_LOAD in [reason.code for reason in result.reasons]


def test_structured_reasons_keep_hazard_and_load_evidence_separate() -> None:
    """The UI gets actual measured values, bands, operators and thresholds."""
    result = classify_checkpoint(
        wind_mph=35,
        rain_in_per_hour=Decimal("1.0001"),
        snow_in_per_hour=0,
        load_weight_lb=Decimal("40000.01"),
    )
    assert result.hazard_level is N and result.load_adjusted_wind_level is S
    assert result.final_level is N
    wind, rain, snow, load = result.reasons
    assert wind.code is ReasonCode.HAZARD_CLASSIFIED and wind.measured_value == Decimal("35")
    assert wind.band is not None and (wind.band.lower, wind.band.upper) == (
        Decimal("35"),
        Decimal("45"),
    )
    assert wind.threshold == Decimal("35") and wind.comparison is Comparison.GE
    assert rain.threshold == Decimal("1.00") and rain.comparison is Comparison.GT
    assert snow.level is L and snow.comparison is Comparison.LT
    assert load.code is ReasonCode.HIGH_WIND_HEAVY_LOAD
    assert load.metric == "load_weight_lb" and load.measured_value == Decimal("40000.01")
    assert load.threshold == Decimal("40000") and load.comparison is Comparison.GT
    assert load.wind_mph == Decimal("35") and load.band == wind.band


def test_results_reasons_and_policy_are_immutable() -> None:
    """Frozen dataclasses, tuples and read-only tables prevent hidden mutations."""
    result = classify_checkpoint(
        wind_mph=45, rain_in_per_hour=0, snow_in_per_hour=0, load_weight_lb=30001
    )
    for target, attribute, value in (
        (result, "final_level", L),
        (result.reasons[0], "measured_value", Decimal("0")),
        (result.reasons[0].band, "lower", Decimal("0")),
        (RISK_POLICY, "maximum_cargo_weight_lb", Decimal("0")),
        (RISK_POLICY.load_rules[0], "resulting_level", L),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(target, attribute, value)
    with pytest.raises(TypeError):
        cast(MutableMapping[Hazard, tuple[RiskBand, ...]], RISK_POLICY.hazard_bands)[
            Hazard.WIND
        ] = ()
    assert isinstance(result.reasons, tuple)
    assert hash(result) == hash(
        classify_checkpoint(
            wind_mph=45,
            rain_in_per_hour=0,
            snow_in_per_hour=0,
            load_weight_lb=30001,
        )
    )


def test_specific_classifiers_and_missing_values() -> None:
    """The simple hazard entry points use the same table and UNKNOWN state."""
    assert classify_wind(25) is M
    assert classify_rain(Decimal(".25")) is H
    assert classify_snow(1) is H
    assert classify_wind(None) is classify_rain(None) is classify_snow(None) is UNKNOWN


@pytest.mark.parametrize(
    "wind,rain,snow,weight,hazard,adjusted,final",
    [
        (10, ".30", "2.5", "0", S, L, S),
        (35, "0", "0", "40000.01", H, S, S),
        (35, "1.0001", "0", "40000.01", N, S, N),
        (30, ".30", "0", "100000", H, M, H),
    ],
)
def test_explanatory_combined_hazard_examples(
    wind: int,
    rain: str,
    snow: str,
    weight: str,
    hazard: RiskLevel,
    adjusted: RiskLevel,
    final: RiskLevel,
) -> None:
    """RISK-05 examples preserve layers; a heavy load never escalates rain or snow."""
    result = classify_checkpoint(
        wind_mph=wind,
        rain_in_per_hour=Decimal(rain),
        snow_in_per_hour=Decimal(snow),
        load_weight_lb=Decimal(weight),
    )
    assert (result.hazard_level, result.load_adjusted_wind_level, result.final_level) == (
        hazard,
        adjusted,
        final,
    )


@pytest.mark.parametrize(
    "wind,weight,code,metric,value,threshold,comparison,level",
    [
        (55, "0", ReasonCode.EXTREME_WIND_ANY_LOAD, "wind_mph", "55", "55", Comparison.GE, N),
        (
            45,
            "30000.01",
            ReasonCode.SEVERE_WIND_HEAVY_LOAD,
            "load_weight_lb",
            "30000.01",
            "30000",
            Comparison.GT,
            N,
        ),
        (
            35,
            "40000.01",
            ReasonCode.HIGH_WIND_HEAVY_LOAD,
            "load_weight_lb",
            "40000.01",
            "40000",
            Comparison.GT,
            S,
        ),
    ],
)
def test_all_load_reason_codes_carry_comparison_evidence(
    wind: int,
    weight: str,
    code: ReasonCode,
    metric: str,
    value: str,
    threshold: str,
    comparison: Comparison,
    level: RiskLevel,
) -> None:
    """Every applicable load rule supplies enough evidence for plain-language UI text."""
    result = classify_checkpoint(
        wind_mph=wind,
        rain_in_per_hour=0,
        snow_in_per_hour=0,
        load_weight_lb=Decimal(weight),
    )
    reason = result.reasons[-1]
    assert reason.code is code and reason.metric == metric
    assert reason.measured_value == Decimal(value) and reason.threshold == Decimal(threshold)
    assert reason.comparison is comparison and reason.level is level
    assert reason.band == result.reasons[0].band
    assert reason.wind_mph == Decimal(wind) and reason.load_weight_lb == Decimal(weight)


def test_missing_wind_explains_why_load_rules_cannot_run() -> None:
    """A missing sustained wind value cannot be replaced with an assumed calm reading."""
    result = classify_checkpoint(
        wind_mph=None,
        rain_in_per_hour=0,
        snow_in_per_hour=0,
        load_weight_lb=100000,
    )
    reason = result.reasons[-1]
    assert reason.code is ReasonCode.LOAD_RULES_UNAVAILABLE_MISSING_WIND
    assert reason.measured_value is None and reason.threshold is None and reason.band is None
    assert reason.level is UNKNOWN and reason.wind_mph is None
    assert reason.load_weight_lb == Decimal("100000")
