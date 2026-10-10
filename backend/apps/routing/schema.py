"""Small authoritative public schema; its rendered TypeScript is checked for drift.

Type expressions deliberately use a small TypeScript subset, also validated by
offline contract tests. No generator dependency or OpenAPI runtime is necessary.
"""

from collections.abc import Iterable, Mapping

from domain.recommendation_types import RecommendationStatus
from domain.risk_types import ReasonCode
from providers.contracts import UnavailableReason

from apps.routing.errors import ERRORS


def literals(values: Iterable[str]) -> str:
    return " | ".join('"' + str(v) + '"' for v in values)


ALIASES = {
    "Position": "[number, number]",
    "RiskLevel": '"LOW" | "MODERATE" | "HIGH" | "SEVERE" | "NO_TRAVEL" | "UNKNOWN"',
    "TravelStatus": '"ASSESSED" | "BLOCKED" | "INCOMPLETE"',
    "RecommendationStatus": literals(s.value for s in RecommendationStatus),
    "UnavailableReason": literals(r.value for r in UnavailableReason),
    "ReasonCode": literals(r.value for r in ReasonCode),
    "ErrorCode": literals(ERRORS),
    "FactValue": "ExactNumber | string | number | boolean | null",
    "NullableExactNumber": "ExactNumber | null",
    "NullableString": "string | null",
}

SCHEMA: dict[str, dict[str, str]] = {
    "ExactNumber": {"numerator": "string", "denominator": "string"},
    "Attribution": {
        "provider": "string",
        "text": "string",
        "confirmed": "boolean",
        "source_url": "string | null",
        "licence_url": "string | null",
    },
    "SelectedPlace": {
        "label": "string",
        "latitude": "number",
        "longitude": "number",
        "candidate_id?": "string",
        "provider?": "string",
        "attribution?": "Attribution",
    },
    "AnalysisRequest": {
        "origin": "SelectedPlace",
        "destination": "SelectedPlace",
        "departure_time": "string",
        "departure_timezone": "string",
        "load_weight_lb": "number",
        "checkpoint_interval_miles?": "10 | 25 | 50",
        "simulation_scenario?": "string | null",
    },
    "HealthResponse": {
        "status": '"ok" | "ready"',
        "version": "string",
        "check": '"liveness" | "readiness"',
    },
    "ErrorDetail": {"code": "ErrorCode", "message": "string", "details": "Record<string, string>"},
    "ErrorResponse": {
        "error": "ErrorDetail",
        "is_simulation?": "boolean",
        "simulation_scenario?": "string | null",
    },
    "Warning": {
        "code": "string",
        "message": "string",
        "scope": "string",
        "coverage_fraction": "ExactNumber | null",
    },
    "ProviderCalls": {"routing": "number", "geocoding": "number", "weather": "number"},
    "CacheDiagnostics": {"hits": "number", "misses": "number", "ages_seconds": "ExactNumber[]"},
    "Metadata": {
        "request_id": "string",
        "total_ms": "number",
        "stage_ms": "Record<string, number>",
        "provider_calls": "ProviderCalls",
        "weather_cache": "CacheDiagnostics",
        "quota_units_reserved": "ExactNumber",
        "deadline_seconds": "number",
        "simulated": "boolean",
    },
    "Candidate": {
        "candidate_id": "string",
        "label": "string",
        "latitude": "number",
        "longitude": "number",
        "region": "string | null",
        "country": "string | null",
        "match_type": "string",
        "score": "ExactNumber",
        "provider": "string",
        "attribution": "Attribution",
    },
    "GeocodeResponse": {
        "candidates": "Candidate[]",
        "attribution": "Attribution",
        "metadata": "Metadata",
    },
    "Trip": {
        "origin": "SelectedPlace",
        "destination": "SelectedPlace",
        "departure_time": "string",
        "departure_timezone": "string",
        "load_weight_lb": "string",
        "reference_time": "string",
        "requested_interval_miles": "number | null",
        "effective_interval_miles": "number",
    },
    "RiskBand": {
        "level": "RiskLevel",
        "printed_pdf_band": "string",
        "lower": "string | null",
        "upper": "string | null",
        "lower_inclusive": "boolean",
        "upper_inclusive": "boolean",
    },
    "RiskReason": {
        "code": "ReasonCode",
        "metric": "string",
        "measured_value": "string | null",
        "band": "RiskBand | null",
        "threshold": "string | null",
        "comparison": "string | null",
        "level": "RiskLevel",
        "wind_mph": "string | null",
        "load_weight_lb": "string | null",
    },
    "RiskResult": {
        "wind_risk": "RiskLevel",
        "rain_risk": "RiskLevel",
        "snow_risk": "RiskLevel",
        "hazard_risk": "RiskLevel",
        "load_adjusted_wind_risk": "RiskLevel",
        "final_risk": "RiskLevel",
        "known_risk_floor": "RiskLevel | null",
        "known_blocked": "boolean",
        "ordinal": "number | null",
        "reasons": "RiskReason[]",
    },
    "WeatherValues": {
        "wind_mph": "string | null",
        "rain_in_hr": "string | null",
        "snow_in_hr": "string | null",
        "gust_mph": "string | null",
    },
    "WeatherSource": {
        "components": "Record<string, NullableExactNumber>",
        "units": "Record<string, NullableString>",
        "hourly_average_rates": "boolean",
    },
    "Weather": {
        "values": "WeatherValues",
        "source": "WeatherSource | null",
        "units": "Record<string, string>",
        "forecast_timestamp": "string",
        "interval_start": "string",
        "interval_end": "string",
        "fetched_at": "string",
        "provider": "string",
        "model": "string",
        "cache_hit": "boolean",
        "unavailable_reason": "UnavailableReason | null",
        "missing_fields": "string[]",
        "hourly_average_rates": "boolean",
    },
    "Checkpoint": {
        "id": "string",
        "index": "number",
        "mile_marker": "ExactNumber",
        "owned_miles": "ExactNumber",
        "elapsed_seconds": "ExactNumber",
        "coordinate": "Position",
        "eta_utc": "string",
        "local_time": "string | null",
        "timezone": "string | null",
        "utc_fallback": "boolean",
        "weather": "Weather",
        "risk": "RiskResult",
    },
    "RiskProfileSegment": {
        "start_mile": "ExactNumber",
        "end_mile": "ExactNumber",
        "final_risk": "RiskLevel",
        "known_risk_floor": "RiskLevel | null",
        "known_blocked": "boolean",
        "checkpoint_id": "string",
    },
    "RouteSummary": {
        "total_miles": "ExactNumber",
        "total_duration_s": "ExactNumber",
        "miles_by_level": "Record<string, ExactNumber>",
        "unknown_miles": "ExactNumber",
        "average_risk": "ExactNumber | null",
        "known_only_average_risk_diagnostic": "ExactNumber | null",
        "maximum_known_level": "RiskLevel | null",
        "known_risk_floor": "RiskLevel | null",
        "no_travel_checkpoint_count": "number",
        "no_travel_miles": "ExactNumber",
        "known_blocked_checkpoint_count": "number",
        "known_blocked_miles_diagnostic": "ExactNumber",
        "known_blocked": "boolean",
        "coverage_fraction": "ExactNumber",
        "travel_status": "TravelStatus",
    },
    "CriterionValues": {
        "no_travel_miles": "ExactNumber",
        "severe_miles": "ExactNumber",
        "high_miles": "ExactNumber",
        "average_risk": "ExactNumber | null",
        "duration_seconds": "ExactNumber",
        "stable_route_id": "string",
    },
    "Route": {
        "route_id": "string",
        "geometry": "Position[]",
        "distance_m": "ExactNumber",
        "duration_s": "ExactNumber",
        "profile": "string",
        "live_traffic": "boolean",
        "attribution": "Attribution",
        "travel_status": "TravelStatus",
        "rank": "number | null",
        "group": "string",
        "criteria": "CriterionValues",
        "checkpoints": "Checkpoint[]",
        "summary": "RouteSummary",
        "risk_profile": "RiskProfileSegment[]",
    },
    "ComparisonFact": {
        "winner_route_id": "string",
        "other_route_id": "string",
        "criterion": "string",
        "winner_value": "FactValue",
        "other_value": "FactValue",
        "code": "string",
    },
    "ExplanationFact": {
        "code": "string",
        "route_id": "string | null",
        "other_route_id": "string | null",
        "values": "Record<string, FactValue>",
    },
    "AnalysisResponse": {
        "analysis_id": "string",
        "policy_version": "string",
        "generated_at": "string",
        "expires_at": "string",
        "trip": "Trip",
        "routes": "Route[]",
        "route_count": "number",
        "recommended_route_id": "string | null",
        "least_blocked_route_id": "string | null",
        "recommendation_status": "RecommendationStatus",
        "message": "string",
        "decisive_criterion": "string",
        "diagnostic_decisive_criterion": "string | null",
        "explanation": "string",
        "comparison_facts": "ComparisonFact[]",
        "explanation_facts": "ExplanationFact[]",
        "is_simulation": "boolean",
        "simulation_scenario": "string | null",
        "warnings": "Warning[]",
        "attributions": "Attribution[]",
        "metadata": "Metadata",
    },
}


def render_typescript(schema: Mapping[str, Mapping[str, str]] = SCHEMA) -> str:
    """Render stable interfaces; CI compares this exact text to the committed types file."""
    lines = [
        "// Shared with backend/apps/routing/schema.py; verified by the offline drift test.",
        "// ExactNumber uses decimal integer strings; never re-rank in the client.",
        "",
    ]
    for name, expression in ALIASES.items():
        lines.extend([f"export type {name} = {expression.replace(chr(34), chr(39))};", ""])
    for name, fields in schema.items():
        lines.append(f"export interface {name} {{")
        lines.extend(
            f"  {key}: {expression.replace(chr(34), chr(39))};"
            for key, expression in fields.items()
        )
        lines.extend(["}", ""])
    return "\n".join(lines)


def check_typescript(text: str, schema: Mapping[str, Mapping[str, str]] = SCHEMA) -> None:
    """Reject field additions/removals/type changes on only one side of the contract."""
    if text != render_typescript(schema):
        raise ValueError("Public Python/TypeScript contract drift")
