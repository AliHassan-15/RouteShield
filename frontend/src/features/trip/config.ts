// Form guards/display hints; the backend owns the supported road-distance envelope.
export const STRAIGHT_LINE_ADVISORY_MILES = 240;
export const MAX_WEIGHT_LB = 100_000;
export const PAST_GRACE_MS = 5 * 60_000;
export const DEPARTURE_WINDOW_MS = 7 * 86_400_000;
export const LABEL_LIMIT = 200;
export const URL_LIMIT = 2048;
export const GEO_DEBOUNCE_MS = 400;
export const GEO_MIN_CHARACTERS = 3;

export const EXAMPLE_TRIPS = [
  { label: 'Chicago, IL to Detroit, MI', origin: { label: 'Chicago, IL', latitude: 41.8781, longitude: -87.6298 }, destination: { label: 'Detroit, MI', latitude: 42.3314, longitude: -83.0458 } },
  { label: 'Santa Monica Pier to Los Angeles City Hall', origin: { label: 'Santa Monica Pier', latitude: 34.0094, longitude: -118.4973 }, destination: { label: 'Los Angeles City Hall', latitude: 34.0537, longitude: -118.2428 } },
] as const;
