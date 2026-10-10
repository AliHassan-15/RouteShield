"""Presentation encoding of the existing risk engine over shared forecast series."""

import gzip
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from typing import cast

from domain.corridor import FRAME_COUNT, FRAME_SECONDS, OPTIONAL_SPACING_MILES, truck_position
from domain.identity import stable_route_id
from domain.risk import classify_checkpoint
from domain.risk_policy import RISK_POLICY
from domain.risk_types import Hazard, Risk, RiskLevel
from domain.route_types import Checkpoint, Route
from providers.contracts import (
    Attribution,
    HourlyWeather,
    PointKey,
    PoolingResult,
    Unavailable,
    UnavailableReason,
    WeatherSeries,
    WeatherValues,
)
from providers.forecast import lookup_forecast

from apps.routing.errors import APIError
from apps.routing.serialization import public, utc_text

FILTER_BUDGET_BYTES = 300_000
PAYLOAD_BUDGET_BYTES = 500_000
LEVEL_LEGEND = {"0": "UNKNOWN", **{str(r.value): r.name for r in RiskLevel}, "9": "Unavailable"}
DOMINANT_LEGEND = {"0": "none", "1": "wind", "2": "rain", "3": "snow", "4": "load_adjusted_wind"}


def digit(level: Risk) -> str:
    """UNKNOWN's wire sentinel is not an ordinal or a safe level."""
    return str(level.value) if isinstance(level, RiskLevel) else "0"


@dataclass(frozen=True)
class Cell:
    level: str
    intensity: int
    dominant: str
    hazards: tuple[str, str, str]
    reason: UnavailableReason | None = None
    known_blocked: bool = False
    known_risk_floor: str = "0"


def intensity(hazard: Hazard, value: Decimal, level: RiskLevel) -> int:
    """Floor exact band progress for display only; load promotions clamp to zero."""
    if level is RiskLevel.NO_TRAVEL:
        return 100
    band = next(b for b in RISK_POLICY.hazard_bands[hazard] if b.level is level)
    lower = Fraction(band.lower or RISK_POLICY.minimum_value)
    assert band.upper is not None
    position = (Fraction(value) - lower) * 100 / (Fraction(band.upper) - lower)
    return max(0, min(100, int(position)))


def classify_cell(value: HourlyWeather | Unavailable, load: Decimal) -> Cell:
    """Reuse checkpoint classification; no data is unavailable, partial data unknown."""
    if isinstance(value, Unavailable):
        return Cell("9", 0, "0", ("9", "9", "9"), value.reason)
    values = value.values
    risk = classify_checkpoint(
        wind_mph=values.wind_mph,
        rain_in_per_hour=values.rain_in_hr,
        snow_in_per_hour=values.snow_in_hr,
        load_weight_lb=load,
    )
    codes = (digit(risk.load_adjusted_wind_level), digit(risk.rain_level), digit(risk.snow_level))
    if risk.known_risk_floor is None:
        return Cell("9", 0, "0", codes, UnavailableReason.MISSING_FIELD)
    if not isinstance(risk.final_level, RiskLevel):
        return Cell(
            "0",
            0,
            "0",
            codes,
            known_blocked=risk.known_blocked,
            known_risk_floor=str(risk.known_risk_floor.value),
        )
    # Fixed wind/rain/snow priority on equal final severity; no gust classification.
    candidates = (
        (Hazard.WIND, values.wind_mph, risk.load_adjusted_wind_level),
        (Hazard.RAIN, values.rain_in_hr, risk.rain_level),
        (Hazard.SNOW, values.snow_in_hr, risk.snow_level),
    )
    index, (hazard, measured, _) = next(
        (i, item) for i, item in enumerate(candidates) if item[2] == risk.final_level
    )
    assert measured is not None
    dominant = (
        "4" if index == 0 and risk.load_adjusted_wind_level != risk.wind_level else str(index + 1)
    )
    return Cell(
        digit(risk.final_level),
        intensity(hazard, measured, risk.final_level),
        dominant,
        codes,
        known_blocked=risk.known_blocked,
        known_risk_floor=str(risk.known_risk_floor.value),
    )


def build_heatmap(
    routes: Sequence[Route],
    checkpoints: Mapping[str, tuple[Checkpoint, ...]],
    pool: PoolingResult,
    series: Sequence[WeatherSeries],
    departure: datetime,
    load: Decimal,
    now: datetime,
    attribution: Attribution,
) -> tuple[dict[str, object], tuple[str, ...]]:
    """49 departure-relative UTC frames; one coordinate list and lossless index maps."""
    departure = departure.astimezone(UTC)
    frames: list[dict[str, object]] = []
    last: list[int | None] = [None] * len(series)
    warnings: list[str] = []
    # Request-local reuse only; cargo is fixed in this invocation, no retained risk cache.
    classified: dict[WeatherValues, Cell] = {}
    for hour in range(FRAME_COUNT):
        instant = departure + timedelta(seconds=hour * FRAME_SECONDS)
        lookups = [lookup_forecast(s, instant, now=now) for s in series]
        cells = []
        for item in lookups:
            if isinstance(item.result, HourlyWeather):
                key = item.result.values
                if key not in classified:
                    classified[key] = classify_cell(item.result, load)
                cells.append(classified[key])
            else:
                cells.append(classify_cell(item.result, load))
        reasons = {str(i): c.reason.value for i, c in enumerate(cells) if c.reason is not None}
        if (
            any(c.level in ("0", "9") for c in cells)
            and "HEATMAP_PARTIAL_AVAILABILITY" not in warnings
        ):
            warnings.append("HEATMAP_PARTIAL_AVAILABILITY")
        if any(c.reason is UnavailableReason.OUT_OF_HORIZON for c in cells):
            if "FORECAST_HORIZON_LIMIT" not in warnings:
                warnings.append("FORECAST_HORIZON_LIMIT")
        for i, cell in enumerate(cells):
            if cell.level != "9":
                last[i] = hour
        frames.append(
            {
                "hour": hour,
                "timestamp": utc_text(instant),
                "levels": "".join(c.level for c in cells),
                "intensities": [c.intensity for c in cells],
                "dominant_hazards": "".join(c.dominant for c in cells),
                "known_blocked": "".join("1" if c.known_blocked else "0" for c in cells),
                "known_risk_floors": "".join(c.known_risk_floor for c in cells),
                "hazard_levels": {
                    name: "".join(c.hazards[index] for c in cells)
                    for index, name in enumerate(("wind", "rain", "snow"))
                },
                "unavailable_reasons": reasons,
            }
        )
    mappings: list[dict[str, object]] = []
    for route in routes:
        route_id = stable_route_id(route)
        mandatory = [
            pool.assignments[PointKey(route_id, i, True)].pooled_index
            for i in range(len(checkpoints[route_id]))
        ]
        optional = [
            {
                "sample_index": key.index,
                "point_index": assignment.pooled_index,
                "coarsened": assignment.coarsened,
                "distance_to_point_m": assignment.distance_m,
            }
            for key, assignment in pool.assignments.items()
            if key.route_id == route_id and not key.mandatory
        ]
        mappings.append(
            {
                "route_id": route_id,
                "checkpoint_point_indices": mandatory,
                "optional_point_mappings": optional,
            }
        )
    if pool.warnings:
        warnings.append("HEATMAP_DENSITY_REDUCED")
    latest = max((h for h in last if h is not None), default=None)
    heatmap: dict[str, object] = {
        "reference_time": utc_text(departure),
        "hour_0_timestamp": utc_text(departure),
        "frame_count": FRAME_COUNT,
        "point_count": len(pool.coordinates),
        "points": [[round(p.longitude, 5), round(p.latitude, 5)] for p in pool.coordinates],
        "frames": frames,
        "route_mappings": mappings,
        "truck_positions": {
            stable_route_id(r): [
                public(truck_position(r, Fraction(h * FRAME_SECONDS))) for h in range(FRAME_COUNT)
            ]
            for r in routes
        },
        "density": {
            "mandatory_point_count": pool.mandatory_count,
            "optional_candidate_count": pool.optional_input_count,
            "optional_selected_count": pool.optional_selected_count,
            "optional_unique_point_count": len(pool.coordinates) - pool.mandatory_count,
            "requested_optional_spacing_miles": OPTIONAL_SPACING_MILES,
            "optional_stride": pool.optional_stride,
            "actual_optional_max_gap_miles": {
                rid: spacing / float(routes[0].policy.meters_per_mile)
                for rid, spacing in pool.actual_spacing_m.items()
            },
            "reduced": bool(pool.warnings),
        },
        "forecast_coverage": {
            "last_usable_hour": latest,
            "last_usable_timestamp": None
            if latest is None
            else utc_text(departure + timedelta(hours=latest)),
            "last_usable_hour_by_point": last,
        },
        "hazard_filters_included": True,
        "hazard_filter_omission_reason": None,
        "legends": {"levels": LEVEL_LEGEND, "dominant_hazards": DOMINANT_LEGEND},
        "intensity_mapping": (
            "floor(100*(value-band_lower)/(band_upper-band_lower)), clamped0..100; "
            "LOW lower=0; NO_TRAVEL=100; UNKNOWN/Unavailable=0 (not calm); "
            "ties wind,rain,snow; load-promoted SEVERE uses final wind band"
        ),
        "attribution": public(attribution),
        "warnings": warnings,
    }
    return heatmap, tuple(warnings)


def compressed_size(payload: dict[str, object]) -> int:
    """Measure compact UTF-8 JSON/gzip without retaining user-specific response bytes."""
    text = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    # Match DRF's escaping as well as its compact JSON separators.
    raw = text.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029").encode()
    return len(gzip.compress(raw, compresslevel=9, mtime=0))


def fit_payload(payload: dict[str, object]) -> None:
    """Enable filters only below300KB; fail explicitly instead of dropping required data."""
    heatmap = cast(dict[str, object], payload["heatmap"])
    if compressed_size(payload) >= FILTER_BUDGET_BYTES:
        for frame in cast(list[dict[str, object]], heatmap["frames"]):
            frame.pop("hazard_levels", None)
        heatmap["hazard_filters_included"] = False
        heatmap["hazard_filter_omission_reason"] = "COMPRESSED_PAYLOAD_AT_LEAST_300KB"
        payload["capabilities"] = {"hazard_filter": False}
    if compressed_size(payload) > PAYLOAD_BUDGET_BYTES:
        raise APIError(
            "TRIP_TOO_LARGE",
            {"max_compressed_bytes": PAYLOAD_BUDGET_BYTES},
            message="This trip exceeds the supported data size for this demo.",
        )
