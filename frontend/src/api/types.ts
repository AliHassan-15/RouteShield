// Shared with backend/apps/routing/schema.py; verified by the offline drift test.
// ExactNumber uses decimal integer strings; never re-rank in the client.

export type Position = [number, number];

export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'SEVERE' | 'NO_TRAVEL' | 'UNKNOWN';

export type TravelStatus = 'ASSESSED' | 'BLOCKED' | 'INCOMPLETE';

export type RecommendationStatus = 'RECOMMENDED' | 'BEST_FULLY_ASSESSED_AVAILABLE' | 'ALL_BLOCKED' | 'NO_FULLY_ASSESSED_TRAVELABLE_ROUTE' | 'ALL_INCOMPLETE';

export type UnavailableReason = 'OUT_OF_HORIZON' | 'MISSING_HOUR' | 'MISSING_FIELD' | 'PAST_TIME' | 'PROVIDER_FAILURE' | 'QUOTA_EXCEEDED' | 'DEMO_QUOTA_REACHED';

export type ReasonCode = 'HAZARD_CLASSIFIED' | 'MISSING_HAZARD' | 'EXTREME_WIND_ANY_LOAD' | 'SEVERE_WIND_HEAVY_LOAD' | 'HIGH_WIND_HEAVY_LOAD' | 'LOAD_RULES_UNAVAILABLE_MISSING_WIND' | 'LOAD_RULES_UNAVAILABLE_MISSING_LOAD' | 'MISSING_LOAD';

export type ErrorCode = 'VALIDATION_ERROR' | 'PAYLOAD_TOO_LARGE' | 'UNSUPPORTED_MEDIA_TYPE' | 'LOCATION_REQUIRES_SELECTION' | 'NO_ROUTE' | 'TRIP_TOO_LARGE' | 'THROTTLED' | 'DEADLINE_EXCEEDED' | 'PROVIDER_TIMEOUT' | 'PROVIDER_UNAVAILABLE' | 'QUOTA_EXCEEDED' | 'PROVIDER_AUTH' | 'MALFORMED_PROVIDER_RESPONSE' | 'INTERNAL_ERROR' | 'METHOD_NOT_ALLOWED' | 'NOT_FOUND' | 'SIMULATION_DISABLED' | 'INVALID_SCENARIO';

export type FactValue = ExactNumber | string | number | boolean | null;

export type NullableExactNumber = ExactNumber | null;

export type NullableString = string | null;

export interface ExactNumber {
  numerator: string;
  denominator: string;
}

export interface Attribution {
  provider: string;
  text: string;
  confirmed: boolean;
  source_url: string | null;
  licence_url: string | null;
}

export interface SelectedPlace {
  label: string;
  latitude: number;
  longitude: number;
  candidate_id?: string;
  provider?: string;
  attribution?: Attribution;
}

export interface AnalysisRequest {
  origin: SelectedPlace;
  destination: SelectedPlace;
  departure_time: string;
  departure_timezone: string;
  load_weight_lb: number;
  checkpoint_interval_miles?: 10 | 25 | 50;
  simulation_scenario?: string | null;
}

export interface HealthResponse {
  status: 'ok' | 'ready';
  version: string;
  check: 'liveness' | 'readiness';
}

export interface ErrorDetail {
  code: ErrorCode;
  message: string;
  details: Record<string, string>;
}

export interface ErrorResponse {
  error: ErrorDetail;
  is_simulation?: boolean;
  simulation_scenario?: string | null;
}

export interface Warning {
  code: string;
  message: string;
  scope: string;
  coverage_fraction: ExactNumber | null;
}

export interface ProviderCalls {
  routing: number;
  geocoding: number;
  weather: number;
}

export interface CacheDiagnostics {
  hits: number;
  misses: number;
  ages_seconds: ExactNumber[];
}

export interface Metadata {
  request_id: string;
  total_ms: number;
  stage_ms: Record<string, number>;
  provider_calls: ProviderCalls;
  weather_cache: CacheDiagnostics;
  quota_units_reserved: ExactNumber;
  deadline_seconds: number;
  simulated: boolean;
}

export interface Candidate {
  candidate_id: string;
  label: string;
  latitude: number;
  longitude: number;
  region: string | null;
  country: string | null;
  match_type: string;
  score: ExactNumber;
  provider: string;
  attribution: Attribution;
}

export interface GeocodeResponse {
  candidates: Candidate[];
  attribution: Attribution;
  metadata: Metadata;
}

export interface Trip {
  origin: SelectedPlace;
  destination: SelectedPlace;
  departure_time: string;
  departure_timezone: string;
  load_weight_lb: string;
  reference_time: string;
  requested_interval_miles: number | null;
  effective_interval_miles: number;
}

export interface RiskBand {
  level: RiskLevel;
  printed_pdf_band: string;
  lower: string | null;
  upper: string | null;
  lower_inclusive: boolean;
  upper_inclusive: boolean;
}

export interface RiskReason {
  code: ReasonCode;
  metric: string;
  measured_value: string | null;
  band: RiskBand | null;
  threshold: string | null;
  comparison: string | null;
  level: RiskLevel;
  wind_mph: string | null;
  load_weight_lb: string | null;
}

export interface RiskResult {
  wind_risk: RiskLevel;
  rain_risk: RiskLevel;
  snow_risk: RiskLevel;
  hazard_risk: RiskLevel;
  load_adjusted_wind_risk: RiskLevel;
  final_risk: RiskLevel;
  known_risk_floor: RiskLevel | null;
  known_blocked: boolean;
  ordinal: number | null;
  reasons: RiskReason[];
}

export interface WeatherValues {
  wind_mph: string | null;
  rain_in_hr: string | null;
  snow_in_hr: string | null;
  gust_mph: string | null;
}

export interface WeatherSource {
  components: Record<string, NullableExactNumber>;
  units: Record<string, NullableString>;
  hourly_average_rates: boolean;
}

export interface Weather {
  values: WeatherValues;
  source: WeatherSource | null;
  units: Record<string, string>;
  forecast_timestamp: string;
  interval_start: string;
  interval_end: string;
  fetched_at: string;
  provider: string;
  model: string;
  cache_hit: boolean;
  unavailable_reason: UnavailableReason | null;
  missing_fields: string[];
  hourly_average_rates: boolean;
}

export interface Checkpoint {
  id: string;
  index: number;
  mile_marker: ExactNumber;
  owned_miles: ExactNumber;
  elapsed_seconds: ExactNumber;
  coordinate: Position;
  eta_utc: string;
  local_time: string | null;
  timezone: string | null;
  utc_fallback: boolean;
  weather: Weather;
  risk: RiskResult;
}

export interface RiskProfileSegment {
  start_mile: ExactNumber;
  end_mile: ExactNumber;
  final_risk: RiskLevel;
  known_risk_floor: RiskLevel | null;
  known_blocked: boolean;
  checkpoint_id: string;
}

export interface RouteSummary {
  total_miles: ExactNumber;
  total_duration_s: ExactNumber;
  miles_by_level: Record<string, ExactNumber>;
  unknown_miles: ExactNumber;
  average_risk: ExactNumber | null;
  known_only_average_risk_diagnostic: ExactNumber | null;
  maximum_known_level: RiskLevel | null;
  known_risk_floor: RiskLevel | null;
  no_travel_checkpoint_count: number;
  no_travel_miles: ExactNumber;
  known_blocked_checkpoint_count: number;
  known_blocked_miles_diagnostic: ExactNumber;
  known_blocked: boolean;
  coverage_fraction: ExactNumber;
  travel_status: TravelStatus;
}

export interface CriterionValues {
  no_travel_miles: ExactNumber;
  severe_miles: ExactNumber;
  high_miles: ExactNumber;
  average_risk: ExactNumber | null;
  duration_seconds: ExactNumber;
  stable_route_id: string;
}

export interface Route {
  route_id: string;
  geometry: Position[];
  distance_m: ExactNumber;
  duration_s: ExactNumber;
  profile: string;
  live_traffic: boolean;
  attribution: Attribution;
  travel_status: TravelStatus;
  rank: number | null;
  group: string;
  criteria: CriterionValues;
  checkpoints: Checkpoint[];
  summary: RouteSummary;
  risk_profile: RiskProfileSegment[];
}

export interface ComparisonFact {
  winner_route_id: string;
  other_route_id: string;
  criterion: string;
  winner_value: FactValue;
  other_value: FactValue;
  code: string;
}

export interface ExplanationFact {
  code: string;
  route_id: string | null;
  other_route_id: string | null;
  values: Record<string, FactValue>;
}

export interface AnalysisResponse {
  analysis_id: string;
  policy_version: string;
  generated_at: string;
  expires_at: string;
  trip: Trip;
  routes: Route[];
  route_count: number;
  recommended_route_id: string | null;
  least_blocked_route_id: string | null;
  recommendation_status: RecommendationStatus;
  message: string;
  decisive_criterion: string;
  diagnostic_decisive_criterion: string | null;
  explanation: string;
  comparison_facts: ComparisonFact[];
  explanation_facts: ExplanationFact[];
  is_simulation: boolean;
  simulation_scenario: string | null;
  warnings: Warning[];
  attributions: Attribution[];
  metadata: Metadata;
}
