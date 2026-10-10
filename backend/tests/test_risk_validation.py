"""Numeric precision, validation errors, determinism and standalone domain use."""

import math
import subprocess
import sys
from decimal import Decimal, localcontext
from pathlib import Path
from typing import cast

import pytest
from domain.risk import classify_checkpoint, classify_hazard, classify_rain
from domain.risk_types import (
    DomainValidationError,
    Hazard,
    NormalizedNumber,
    RiskLevel,
    ValidationCode,
)


@pytest.mark.parametrize(
    "field", ["wind_mph", "rain_in_per_hour", "snow_in_per_hour", "load_weight_lb"]
)
@pytest.mark.parametrize(
    "value,code",
    [
        (-1, ValidationCode.NEGATIVE_VALUE),
        (Decimal("-.0001"), ValidationCode.NEGATIVE_VALUE),
        (float("nan"), ValidationCode.NON_FINITE_VALUE),
        (float("inf"), ValidationCode.NON_FINITE_VALUE),
        (float("-inf"), ValidationCode.NON_FINITE_VALUE),
        (Decimal("NaN"), ValidationCode.NON_FINITE_VALUE),
        (Decimal("sNaN"), ValidationCode.NON_FINITE_VALUE),
        (Decimal("Infinity"), ValidationCode.NON_FINITE_VALUE),
        (Decimal("-Infinity"), ValidationCode.NON_FINITE_VALUE),
        (True, ValidationCode.INVALID_NUMBER_TYPE),
        (False, ValidationCode.INVALID_NUMBER_TYPE),
        ("0.1", ValidationCode.INVALID_NUMBER_TYPE),
        (complex(1, 0), ValidationCode.INVALID_NUMBER_TYPE),
    ],
)
def test_invalid_numbers_are_domain_errors(field: str, value: object, code: ValidationCode) -> None:
    """Invalid numeric input is distinct from a missing observation, on every field."""
    inputs: dict[str, NormalizedNumber | None] = dict.fromkeys(
        ["wind_mph", "rain_in_per_hour", "snow_in_per_hour", "load_weight_lb"], 0
    )
    inputs[field] = cast(NormalizedNumber, value)
    with pytest.raises(DomainValidationError) as error:
        classify_checkpoint(**inputs)
    assert error.value.code is code and error.value.field == field
    assert str(error.value).startswith(field + ": ")


@pytest.mark.parametrize("hazard", list(Hazard))
@pytest.mark.parametrize("value", [True, -1, Decimal("sNaN")])
def test_individual_classifiers_validate(hazard: Hazard, value: NormalizedNumber) -> None:
    """Direct hazard calls cannot bypass checkpoint validation."""
    with pytest.raises(DomainValidationError):
        classify_hazard(hazard, value)


@pytest.mark.parametrize("weight", [Decimal("100000.0001"), 100001, Decimal("1e1000")])
def test_excessive_load_rejected(weight: NormalizedNumber) -> None:
    """D20's upper cargo guard is inclusive and applied even in known blocking wind."""
    with pytest.raises(DomainValidationError) as error:
        classify_checkpoint(
            wind_mph=55, rain_in_per_hour=0, snow_in_per_hour=0, load_weight_lb=weight
        )
    assert error.value.code is ValidationCode.LOAD_WEIGHT_OUT_OF_RANGE


@pytest.mark.parametrize("weight", [0, 100000, Decimal("100000.0000")])
def test_load_envelope_endpoints_are_valid(weight: NormalizedNumber) -> None:
    """Zero and the exact maximum are accepted, without a legal weight claim."""
    result = classify_checkpoint(
        wind_mph=0, rain_in_per_hour=0, snow_in_per_hour=0, load_weight_lb=weight
    )
    assert result.final_level is RiskLevel.LOW


@pytest.mark.parametrize(
    "wind,weight,expected",
    [
        (45, Decimal("30000.5"), RiskLevel.NO_TRAVEL),
        (35, Decimal("40000.5"), RiskLevel.SEVERE),
        (
            45,
            Decimal("30000.000000000000000000000000000000000000000000000000001"),
            RiskLevel.NO_TRAVEL,
        ),
        (
            35,
            Decimal("40000.000000000000000000000000000000000000000000000000001"),
            RiskLevel.SEVERE,
        ),
        (45, 30000.5, RiskLevel.NO_TRAVEL),
    ],
)
def test_decimal_weights_are_preserved(
    wind: int, weight: NormalizedNumber, expected: RiskLevel
) -> None:
    """Neither integer coercion nor Decimal-context rounding can erase a strict excess."""
    result = classify_checkpoint(
        wind_mph=wind, rain_in_per_hour=0, snow_in_per_hour=0, load_weight_lb=weight
    )
    assert result.final_level is expected
    assert result.reasons[-1].measured_value == Decimal(str(weight))


@pytest.mark.parametrize(
    "value,expected",
    [
        (0.1, RiskLevel.MODERATE),
        (0.25, RiskLevel.HIGH),
        (0.5, RiskLevel.SEVERE),
        (1.0, RiskLevel.SEVERE),
        (1.0001, RiskLevel.NO_TRAVEL),
    ],
)
def test_float_literals_at_boundaries(value: float, expected: RiskLevel) -> None:
    """Canonical float text agrees with the exact decimal threshold literals."""
    assert classify_rain(value) is expected


@pytest.mark.parametrize(
    "hazard,boundary",
    [
        (Hazard.WIND, 25.0),
        (Hazard.WIND, 35.0),
        (Hazard.WIND, 45.0),
        (Hazard.WIND, 55.0),
        (Hazard.RAIN, 0.1),
        (Hazard.RAIN, 0.25),
        (Hazard.RAIN, 0.5),
        (Hazard.SNOW, 0.5),
        (Hazard.SNOW, 1.0),
        (Hazard.SNOW, 2.0),
    ],
)
def test_next_representable_float_is_not_shifted(hazard: Hazard, boundary: float) -> None:
    """Even the closest float below a lower-inclusive cutoff stays in the lower band."""
    below = classify_hazard(hazard, math.nextafter(boundary, -math.inf))
    exact = classify_hazard(hazard, boundary)
    above = classify_hazard(hazard, math.nextafter(boundary, math.inf))
    assert isinstance(below, RiskLevel) and isinstance(exact, RiskLevel)
    assert below < exact and above is exact


@pytest.mark.parametrize("hazard,boundary", [(Hazard.RAIN, 1.0), (Hazard.SNOW, 3.0)])
def test_next_float_at_strict_upper_cutoff(hazard: Hazard, boundary: float) -> None:
    """No epsilon shift permits a value actually above a strict upper bound."""
    assert classify_hazard(hazard, math.nextafter(boundary, -math.inf)) is RiskLevel.SEVERE
    assert classify_hazard(hazard, boundary) is RiskLevel.SEVERE
    assert classify_hazard(hazard, math.nextafter(boundary, math.inf)) is RiskLevel.NO_TRAVEL


def test_decimal_sums_do_not_inherit_binary_float_artifacts() -> None:
    """Exact decimal normalization works; already-rounded binary sums are not guessed."""
    assert classify_rain(Decimal(".05") + Decimal(".05")) is RiskLevel.MODERATE
    assert classify_rain(Decimal(".10") + Decimal(".15")) is RiskLevel.HIGH
    assert classify_rain(sum([Decimal(".05")] * 10)) is RiskLevel.SEVERE
    assert classify_rain(Decimal(".1") + Decimal(".2") + Decimal(".7")) is RiskLevel.SEVERE
    # Sequential addition deliberately exercises a binary artifact; Python 3.12's
    # improved float sum() may recover the exact boundary instead.
    below_half = 0.0
    for _ in range(10):
        below_half += 0.05
    assert below_half < 0.5
    assert classify_rain(below_half) is RiskLevel.HIGH
    # A real floating value is respected rather than corrected to its presumed intention.
    assert classify_rain(below_half) is classify_rain(Decimal(str(below_half)))


def test_determinism_ignores_decimal_context() -> None:
    """Existing input precision is preserved even under a caller's tiny context."""
    inputs = dict(
        wind_mph=Decimal("35"),
        rain_in_per_hour=Decimal(".25"),
        snow_in_per_hour=Decimal("0"),
        load_weight_lb=Decimal("40000.000000000000000000000000000000000000000001"),
    )
    expected = classify_checkpoint(**inputs)
    for precision in (2, 6, 28, 60):
        with localcontext() as context:
            context.prec = precision
            assert classify_checkpoint(**inputs) == expected
    assert expected.final_level is RiskLevel.SEVERE


def test_domain_runs_without_framework_or_network_imports() -> None:
    """A fresh isolated interpreter proves runtime purity, alongside the AST guard."""
    backend = Path(__file__).resolve().parents[1]
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "from domain.risk import classify_checkpoint; "
        "r = classify_checkpoint(wind_mph=55, rain_in_per_hour=None, "
        "snow_in_per_hour=0, load_weight_lb=0); "
        "assert r.known_blocked and r.final_level.ordinal is None; "
        "assert not ({'django', 'rest_framework', 'httpx', 'requests', 'http', 'urllib', 'socket', "
        "'apps', 'config', 'providers'} & {name.split('.')[0] for name in sys.modules})"
    )
    subprocess.run([sys.executable, "-I", "-c", code, str(backend)], check=True, cwd=backend)
