"""Injected offline-testable orchestration; no provider-specific weather assumptions."""

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from fractions import Fraction
from typing import TypeVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from domain.aggregation import aggregate_route
from domain.checkpoints import candidate_intervals, generate_checkpoints
from domain.corridor import corridor_samples
from domain.identity import stable_route_id
from domain.recommendation import recommend_routes
from domain.recommendation_types import RankingInput
from domain.risk import classify_checkpoint
from domain.risk_types import CheckpointRisk
from domain.route_policy import DEFAULT_MAX_ROUTE_DISTANCE_MILES, DEFAULT_ROUTE_POLICY
from domain.route_types import Checkpoint, Coordinate, Route, RouteError
from providers.contracts import (
    Attribution,
    GeocodingProvider,
    HourlyWeather,
    PointKey,
    PoolingResult,
    PoolPoint,
    RoutingProvider,
    Unavailable,
    UnavailableReason,
    WeatherDiagnostics,
    WeatherProvider,
    WeatherResult,
    WeatherSeries,
)
from providers.deadline import Deadline
from providers.distinctness import point_distance
from providers.errors import ProviderError
from providers.forecast import forecast_window, lookup_forecast
from providers.pooling import pool_coordinates
from providers.quota import QuotaLedger
from providers.weather import WEATHER_ATTRIBUTION
from providers.weather_normalization import unavailable_series

from apps.routing.errors import APIError, provider_error
from apps.routing.heatmap import build_heatmap, fit_payload
from apps.routing.serialization import epoch_text, public, risk_result, utc_text
from apps.routing.validation import Trip, validate_query, validate_trip

T = TypeVar("T")
POLICY_VERSION = "D01-D24-2026-10-11"
STRAIGHT_LINE_ENVELOPE_RATIO = Fraction(4, 5)
# This is an operational completion allowance, never extra upstream time.
COMPLETION_MARGIN_SECONDS = 0.5
BASEMAP_ATTRIBUTIONS = (
    Attribution("OpenFreeMap", "Basemap by OpenFreeMap", True, "https://openfreemap.org/"),
    Attribution("OpenMapTiles", "© OpenMapTiles", True, "https://openmaptiles.org/"),
    Attribution(
        "OpenStreetMap",
        "© OpenStreetMap contributors",
        True,
        "https://www.openstreetmap.org/copyright",
    ),
)
WARNING_MESSAGES = {
    "PARTIAL_ROUTES": "Fewer than three distinct routes are available.",
    "INTERVAL_INCREASED": "Checkpoint spacing was increased to fit 200 unique locations.",
    "INCOMPLETE_WEATHER": "Weather coverage is incomplete; UNKNOWN is never treated as safe.",
    "FORECAST_HORIZON_LIMIT": "Some arrival times are outside the returned forecast horizon.",
    "DEMO_QUOTA_REACHED": "Demo weather quota reached; try again after the quota window resets.",
    "WEATHER_UNAVAILABLE": "Weather could not be obtained for some locations.",
    "DEADLINE_WEATHER_UNAVAILABLE": "The time budget ended; remaining weather is unavailable.",
    "BLOCKED_TRIP": "No safe route at this departure time and load.",
    "UTC_FALLBACK": "Geographic timezone is unavailable; checkpoint times are labeled UTC.",
    "ROUTING_DEPARTURE_ADJUSTED": (
        "The provider rejected a past departure; routing used current time; "
        "ETAs retain the submitted departure."
    ),
    "FALLBACK_SKIPPED_DEADLINE": "Additional route search could not fit the remaining time budget.",
    "FALLBACK_UNAVAILABLE": "Additional route search was unavailable.",
    "HEATMAP_DENSITY_REDUCED": "Optional corridor samples were coarsened to fit 200 locations.",
    "HEATMAP_PARTIAL_AVAILABILITY": (
        "Some forecast cells are unknown or unavailable; they are never calm."
    ),
}


@dataclass
class RequestContext:
    request_id: str
    started: float
    now: datetime
    deadline: Deadline
    deadline_seconds: float
    stages: dict[str, float] = field(default_factory=dict)
    cache: WeatherDiagnostics = field(default_factory=lambda: WeatherDiagnostics(0, 0, (), 0))


class AnalysisService:
    """One service per process; only the forecast adapter retains weather cache entries."""

    def __init__(
        self,
        *,
        geocoder: GeocodingProvider,
        router: RoutingProvider,
        weather: WeatherProvider,
        ledger: QuotaLedger,
        clock: Callable[[], datetime],
        monotonic: Callable[[], float],
        deadline_factory: Callable[[], Deadline],
        request_id: Callable[[], str],
        deadline_seconds: float = 35,
        max_coordinates: int = 200,
        max_route_distance_miles: float = DEFAULT_MAX_ROUTE_DISTANCE_MILES,
    ) -> None:
        self.geocoder, self.router, self.weather, self.ledger = geocoder, router, weather, ledger
        self.clock, self.monotonic = clock, monotonic
        self.deadline_factory, self.request_id = deadline_factory, request_id
        self.deadline_seconds, self.max_coordinates = deadline_seconds, max_coordinates
        self.max_route_distance_miles = Fraction(str(max_route_distance_miles))
        # A bounded shared executor also bounds caller waits for an uncooperative fake/adapter.
        # Running providers retain their own limiter slots and cooperatively see cancellation.
        self._workers = ThreadPoolExecutor(max_workers=4, thread_name_prefix="api-provider")

    def begin(self) -> RequestContext:
        started = self.monotonic()
        deadline = self.deadline_factory()
        return RequestContext(
            self.request_id(), started, self.clock(), deadline, self.deadline_seconds
        )

    @contextmanager
    def stage(self, context: RequestContext, name: str) -> Iterator[None]:
        start = self.monotonic()
        try:
            yield
        finally:
            context.stages[name] = max(0, (self.monotonic() - start) * 1000)

    def metadata(self, context: RequestContext) -> dict[str, object]:
        calls, reserved = context.deadline.metrics()
        return {
            "request_id": context.request_id,
            "total_ms": max(0, (self.monotonic() - context.started) * 1000),
            "stage_ms": dict(context.stages),
            "provider_calls": calls,
            "weather_cache": {
                "hits": context.cache.cache_hits,
                "misses": context.cache.cache_misses,
                "ages_seconds": public(context.cache.ages_seconds),
            },
            "quota_units_reserved": public(reserved),
            "deadline_seconds": context.deadline_seconds,
            "simulated": False,
        }

    def _bounded(
        self,
        context: RequestContext,
        operation: Callable[[], T],
        *,
        retain_partial_weather: bool = False,
    ) -> T:
        if context.deadline.remaining() <= 0:
            raise APIError("DEADLINE_EXCEEDED")
        future = self._workers.submit(operation)
        try:
            value = future.result(timeout=context.deadline.remaining())
        except FutureTimeout:
            context.deadline.cancel()
            future.cancel()
            raise APIError("DEADLINE_EXCEEDED") from None
        except ProviderError as error:
            raise provider_error(error, expired=context.deadline.remaining() <= 0) from None
        if context.deadline.remaining() <= 0 and not retain_partial_weather:
            raise APIError("DEADLINE_EXCEEDED")
        return value

    def geocode(self, params: dict[str, object], context: RequestContext) -> dict[str, object]:
        with self.stage(context, "validation"):
            query = validate_query(params)
        with self.stage(context, "geocoding"):
            result = self._bounded(
                context, lambda: self.geocoder.geocode(query, deadline=context.deadline)
            )
        candidates = [
            {
                "candidate_id": c.candidate_id,
                "label": c.label,
                "longitude": c.coordinate.longitude,
                "latitude": c.coordinate.latitude,
                "region": c.region,
                "country": c.country,
                "match_type": c.match_type,
                "score": public(c.score),
                "provider": result.attribution.provider,
                "attribution": public(result.attribution),
            }
            for c in result.candidates
        ]
        return {
            "candidates": candidates,
            "attribution": public(result.attribution),
            "metadata": self.metadata(context),
        }

    def _checkpoints(
        self, routes: tuple[Route, ...], trip: Trip, context: RequestContext
    ) -> tuple[int, dict[str, tuple[Checkpoint, ...]], PoolingResult, int]:
        options = candidate_intervals(routes, trip.interval)
        for interval in options:
            checkpoints = {
                stable_route_id(r): generate_checkpoints(
                    r, trip.departure, interval, check_budget=False
                )
                for r in routes
            }
            points = [
                PoolPoint(PointKey(route_id, i, True), cp.coordinate, cp.distance_m)
                for route_id, cps in checkpoints.items()
                for i, cp in enumerate(cps)
            ]
            optional = [
                PoolPoint(PointKey(route_id, i, False), coordinate, distance)
                for route in routes
                for route_id in (stable_route_id(route),)
                for i, (distance, coordinate) in enumerate(
                    corridor_samples(route, checkpoints[route_id])
                )
            ]
            try:
                pool = pool_coordinates(points, optional, cap=self.max_coordinates)
                return interval, checkpoints, pool, options[0]
            except RouteError as error:
                if error.code != "TRIP_TOO_LARGE":
                    raise
        raise APIError("TRIP_TOO_LARGE")

    def analyze(self, value: object, context: RequestContext) -> dict[str, object]:
        with self.stage(context, "validation"):
            trip = validate_trip(value, context.now)
            straight_miles = (
                Fraction(
                    str(
                        point_distance(
                            trip.origin.coordinate,
                            trip.destination.coordinate,
                            float(DEFAULT_ROUTE_POLICY.earth_radius_m),
                        )
                    )
                )
                / DEFAULT_ROUTE_POLICY.meters_per_mile
            )
            if straight_miles > STRAIGHT_LINE_ENVELOPE_RATIO * self.max_route_distance_miles:
                raise self._envelope_error()
        with self.stage(context, "routing"):
            result = self._bounded(
                context,
                lambda: self.router.route_alternatives(
                    trip.origin.coordinate,
                    trip.destination.coordinate,
                    trip.departure,
                    deadline=context.deadline,
                ),
            )
        if not result.routes:
            raise APIError("NO_ROUTE")
        if min(r.distance_miles for r in result.routes) > self.max_route_distance_miles:
            raise self._envelope_error()
        # Provider order never becomes public identity or a tie-breaker.
        routes = tuple(sorted(result.routes, key=stable_route_id))
        warnings: list[dict[str, object]] = []

        def warn(code: str, scope: str = "trip", coverage: Fraction | None = None) -> None:
            warning = {
                "code": code,
                "message": WARNING_MESSAGES[code],
                "scope": scope,
                "coverage_fraction": public(coverage),
            }
            if warning not in warnings:
                warnings.append(warning)

        for warning in result.warnings:
            if warning.code in WARNING_MESSAGES:
                warn(warning.code)
        if len(routes) < 3:
            warn("PARTIAL_ROUTES")
        try:
            with self.stage(context, "checkpoints_and_pooling"):
                interval, checkpoints, pool, initial = self._checkpoints(routes, trip, context)
        except ProviderError as error:
            raise provider_error(error, expired=context.deadline.remaining() <= 0) from None
        if interval != initial:
            warn("INTERVAL_INCREASED")
        window = forecast_window(
            trip.departure, max(cp.eta_utc for cps in checkpoints.values() for cp in cps)
        )
        with self.stage(context, "weather"):
            weather: WeatherResult | None = None
            try:
                weather = self._bounded(
                    context,
                    lambda: self.weather.fetch(pool.coordinates, window, deadline=context.deadline),
                    retain_partial_weather=True,
                )
                if len(weather.series) != len(pool.coordinates) or any(
                    s.coordinate != p for s, p in zip(weather.series, pool.coordinates, strict=True)
                ):
                    raise APIError("MALFORMED_PROVIDER_RESPONSE")
            except Exception:
                weather = None
                warn(
                    "DEADLINE_WEATHER_UNAVAILABLE"
                    if context.deadline.remaining() <= 0
                    else "WEATHER_UNAVAILABLE"
                )
            if weather is None:
                series = tuple(
                    unavailable_series(
                        p,
                        window,
                        UnavailableReason.PROVIDER_FAILURE,
                        model="unavailable",
                        fetched_at=self.clock(),
                    )
                    for p in pool.coordinates
                )
                attribution = WEATHER_ATTRIBUTION
            else:
                series, attribution, context.cache = (
                    weather.series,
                    weather.attribution,
                    weather.diagnostics,
                )
                if context.deadline.remaining() <= 0:
                    warn("DEADLINE_WEATHER_UNAVAILABLE")
        route_data: dict[str, dict[str, object]] = {}
        inputs: list[RankingInput] = []
        with self.stage(context, "risk_and_aggregation"):
            for route in routes:
                route_id = stable_route_id(route)
                cps = checkpoints[route_id]
                cp_data: list[dict[str, object]] = []
                risks = []
                profiles = []
                for i, cp in enumerate(cps):
                    s = series[pool.assignments[PointKey(route_id, i, True)].pooled_index]
                    data, risk = self._checkpoint(
                        route_id, i, cp, s, trip, route.policy.meters_per_mile
                    )
                    cp_data.append(data)
                    risks.append(risk)
                    profiles.append(
                        {
                            "start_mile": public(cp.ownership.start_miles),
                            "end_mile": public(cp.ownership.end_miles),
                            "final_risk": public(risk.final_level),
                            "known_risk_floor": public(risk.known_risk_floor),
                            "known_blocked": risk.known_blocked,
                            "checkpoint_id": data["id"],
                        }
                    )
                    if data["utc_fallback"]:
                        warn("UTC_FALLBACK")
                    lookup = lookup_forecast(s, cp.eta_utc, now=self.clock())
                    if isinstance(lookup.result, Unavailable):
                        reason = lookup.result.reason
                        if reason is UnavailableReason.OUT_OF_HORIZON:
                            warn("FORECAST_HORIZON_LIMIT", route_id)
                        elif reason is UnavailableReason.DEMO_QUOTA_REACHED:
                            warn("DEMO_QUOTA_REACHED")
                        elif reason in (
                            UnavailableReason.PROVIDER_FAILURE,
                            UnavailableReason.QUOTA_EXCEEDED,
                        ):
                            warn("WEATHER_UNAVAILABLE", route_id)
                summary = aggregate_route(route, cps, risks)
                inputs.append(RankingInput(route, summary))
                if summary.unknown_miles:
                    warn("INCOMPLETE_WEATHER", route_id, summary.coverage_fraction)
                route_data[route_id] = {
                    "route_id": route_id,
                    "geometry": public(route.geometry),
                    "distance_m": public(route.distance_m),
                    "duration_s": public(route.duration_s),
                    "profile": result.profile,
                    "live_traffic": result.live_traffic,
                    "attribution": public(result.attribution),
                    "checkpoints": cp_data,
                    "summary": public(summary),
                    "risk_profile": profiles,
                }
        with self.stage(context, "ranking_and_explanation"):
            ranking = recommend_routes(inputs)
            if ranking.recommendation_status.value == "ALL_BLOCKED":
                warn("BLOCKED_TRIP")
            output = []
            for row in ranking.routes:
                output.append(
                    {
                        **route_data[row.route_id],
                        "travel_status": row.travel_status.value,
                        "rank": row.rank,
                        "group": row.group.value,
                        "criteria": public(row.criteria),
                    }
                )
        generated = self.clock()
        with self.stage(context, "heatmap"):
            heatmap, heatmap_warnings = build_heatmap(
                routes, checkpoints, pool, series, trip.departure, trip.load, generated, attribution
            )
        for code in heatmap_warnings:
            warn(code, "heatmap")
        # A snapshot is only as fresh as its oldest underlying series; no route result cache.
        expires = min(s.provenance.fetched_at for s in series) + 900
        payload = {
            "analysis_id": context.request_id,
            "policy_version": POLICY_VERSION,
            "generated_at": utc_text(generated),
            "expires_at": epoch_text(expires),
            "trip": {
                "origin": self._place(trip.origin.label, trip.origin.coordinate),
                "destination": self._place(trip.destination.label, trip.destination.coordinate),
                "departure_time": utc_text(trip.departure),
                "departure_timezone": trip.timezone,
                "load_weight_lb": str(trip.load),
                "reference_time": utc_text(trip.departure),
                "requested_interval_miles": trip.interval,
                "effective_interval_miles": interval,
            },
            "routes": output,
            "route_count": ranking.route_count,
            "recommended_route_id": ranking.recommended_route_id,
            "least_blocked_route_id": ranking.least_blocked_route_id,
            "recommendation_status": ranking.recommendation_status.value,
            "message": ranking.message,
            "decisive_criterion": ranking.decisive_criterion.value,
            "diagnostic_decisive_criterion": public(ranking.diagnostic_decisive_criterion),
            "explanation": ranking.explanation,
            "comparison_facts": public(ranking.comparison_facts),
            "explanation_facts": public(ranking.explanation_facts),
            "is_simulation": False,
            "simulation_scenario": None,
            "warnings": warnings,
            "attributions": public((result.attribution, attribution, *BASEMAP_ATTRIBUTIONS)),
            "metadata": self.metadata(context),
            "heatmap": heatmap,
            "capabilities": {"hazard_filter": True},
        }
        fit_payload(payload)
        return payload

    def _envelope_error(self) -> APIError:
        return APIError(
            "TRIP_TOO_LARGE",
            {"max_distance_miles": float(self.max_route_distance_miles)},
            message="The trip is longer than the supported distance for this demo.",
        )

    @staticmethod
    def _place(label: str, coordinate: Coordinate) -> dict[str, object]:
        return {"label": label, "longitude": coordinate.longitude, "latitude": coordinate.latitude}

    def _checkpoint(
        self,
        route_id: str,
        index: int,
        cp: Checkpoint,
        series: WeatherSeries,
        trip: Trip,
        meters_per_mile: Fraction,
    ) -> tuple[dict[str, object], CheckpointRisk]:
        lookup = lookup_forecast(series, cp.eta_utc, now=self.clock())
        sample = lookup.result
        values = sample.values if isinstance(sample, HourlyWeather) else sample.known_values
        risk = classify_checkpoint(
            wind_mph=values.wind_mph,
            rain_in_per_hour=values.rain_in_hr,
            snow_in_per_hour=values.snow_in_hr,
            load_weight_lb=trip.load,
        )
        zone = None
        if not series.timezone_fallback:
            try:
                zone = ZoneInfo(series.timezone)
            except (ZoneInfoNotFoundError, ValueError):
                pass
        return {
            "id": f"{route_id}:{index}",
            "index": index,
            "coordinate": public(cp.coordinate),
            "mile_marker": public(cp.distance_m / meters_per_mile),
            "owned_miles": public(cp.owned_miles),
            "elapsed_seconds": public(cp.elapsed_s),
            "eta_utc": utc_text(cp.eta_utc),
            "local_time": cp.eta_utc.astimezone(zone).isoformat() if zone else None,
            "timezone": series.timezone if zone else None,
            "utc_fallback": zone is None,
            "weather": {
                "values": public(values),
                "source": public(sample.source),
                "units": {"wind": "mph", "rain": "in/hr", "snow": "in/hr", "gust": "mph"},
                "forecast_timestamp": utc_text(datetime.fromtimestamp(lookup.forecast_epoch, UTC)),
                "interval_start": epoch_text(lookup.forecast_epoch - 3600),
                "interval_end": epoch_text(lookup.forecast_epoch),
                "fetched_at": epoch_text(series.provenance.fetched_at),
                "provider": series.provenance.provider,
                "model": series.provenance.model,
                "cache_hit": series.provenance.cache_hit,
                "unavailable_reason": sample.reason.value
                if isinstance(sample, Unavailable)
                else None,
                "missing_fields": list(sample.missing_fields)
                if isinstance(sample, Unavailable)
                else [],
                "hourly_average_rates": True,
            },
            "risk": risk_result(risk),
        }, risk

    def close(self) -> None:
        """Tests release queued work; never wait for cancelled provider calls."""
        self._workers.shutdown(wait=False, cancel_futures=True)
