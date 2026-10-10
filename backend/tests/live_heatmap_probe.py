"""Opt-in local HTTP measurement; prints numeric summaries, never provider data."""

import gzip
import http.client
import io
import json
import logging
import os
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from typing import Any, cast
from urllib.parse import urlsplit
from wsgiref.simple_server import WSGIRequestHandler, make_server

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402 -- CLI initialization must precede Django imports.

django.setup()

from apps.routing.factory import get_service  # noqa: E402
from apps.routing.service import RequestContext  # noqa: E402
from django.core.wsgi import get_wsgi_application  # noqa: E402
from providers.errors import ErrorCode, ProviderError  # noqa: E402
from providers.tomtom import TomTomRouter  # noqa: E402
from providers.transport import HttpxClient  # noqa: E402
from providers.weather import OpenMeteoWeather  # noqa: E402


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        """Avoid local URL/access logs too."""

    def get_stderr(self) -> io.StringIO:
        return io.StringIO()


def main() -> None:
    """One analysis; carry prior numeric budget totals into an authorized second process."""
    reduced = "--reduced" in sys.argv
    carried = (
        json.loads(sys.argv[sys.argv.index("--carried") + 1]) if "--carried" in sys.argv else {}
    )
    service = get_service()
    router = cast(TomTomRouter, service.router)
    weather = cast(OpenMeteoWeather, service.weather)
    client = cast(HttpxClient, weather.transport.client)
    original_get, original_reserve = client.get, service.ledger.reserve
    lock = threading.Lock()
    used: dict[str, int | Fraction] = {
        "tomtom": int(carried.get("tomtom", 0)),
        "weather": int(carried.get("weather", 0)),
        "units": Fraction(str(carried.get("units", 0))),
    }
    before = dict(used)
    coordinates = 0
    contexts: list[RequestContext] = []
    original_begin = service.begin

    def begin() -> Any:
        context = original_begin()
        contexts.append(context)
        return context

    def send(url: str, **kwargs: Any) -> Any:
        nonlocal coordinates
        host = urlsplit(url).hostname
        provider = {"api.tomtom.com": "tomtom", "api.open-meteo.com": "weather"}.get(host or "")
        if provider is None:
            raise ProviderError(ErrorCode.INVALID_REQUEST)
        with lock:
            if used[provider] >= (6 if provider == "tomtom" else 4):
                raise ProviderError(ErrorCode.QUOTA_EXCEEDED)
            used[provider] += 1
            if provider == "weather":
                coordinates += next(
                    str(v).count(",") + 1 for k, v in kwargs["params"] if k == "latitude"
                )
        return original_get(url, **kwargs)

    def reserve(units: Fraction) -> Any:
        with lock:
            if used["units"] + units > 600:
                return None
            reservation = original_reserve(units)
            if reservation is not None:
                used["units"] += units
            return reservation

    # Instrument the existing adapters only; no timeout/configuration replacement.
    client.get = send  # type: ignore[method-assign]
    service.ledger.reserve = reserve  # type: ignore[method-assign]
    service.begin = begin  # type: ignore[method-assign]
    server = make_server("127.0.0.1", 0, get_wsgi_application(), handler_class=QuietHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    logging.getLogger("django.server").disabled = True
    departure = (datetime.now(UTC) + timedelta(hours=3)).replace(microsecond=0)
    origin, destination = (
        ((41.8781, -87.6298), (42.3314, -83.0458))
        if reduced
        else ((43.0389, -87.9065), (42.3314, -83.0458))
    )
    body = {
        "origin": {
            "label": "Chicago" if reduced else "Milwaukee",
            "latitude": origin[0],
            "longitude": origin[1],
        },
        "destination": {
            "label": "Detroit",
            "latitude": destination[0],
            "longitude": destination[1],
        },
        "departure_time": departure.isoformat(),
        "departure_timezone": "UTC",
        "load_weight_lb": 45000,
    }
    print(
        json.dumps(
            {
                "effective": {
                    "routing_read_s": router._transport.config.routing_read_seconds,
                    "weather_read_s": weather.config.read_seconds,
                    "envelope_miles": float(service.max_route_distance_miles),
                    "deadline_s": service.deadline_seconds,
                }
            }
        ),
        flush=True,
    )
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=45)
    try:
        started = time.perf_counter()
        connection.request(
            "POST",
            "/api/v1/route-analysis/",
            json.dumps(body).encode(),
            {"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        raw = response.read()
        wall = time.perf_counter() - started
        data = json.loads(raw)
        metadata = service.metadata(contexts[-1]) if contexts else {}
        routes = data.get("routes", [])
        heatmap = data.get("heatmap", {})
        record = {
            "corridor": "Chicago-Detroit" if reduced else "Milwaukee-Detroit",
            "departure_utc": departure.isoformat(),
            "http_status": response.status,
            "error_code": data.get("error", {}).get("code"),
            "wall_s": round(wall, 6),
            "stage_ms": metadata.get("stage_ms", {}),
            "route_count": len(routes),
            "three_distinct": len(routes) == 3 and len({r["route_id"] for r in routes}) == 3,
            "distinctness_source": "Existing production D09 filtering of accepted adapter routes",
            "fallback_calls": max(0, int(used["tomtom"] - before["tomtom"]) - 1),
            "provider_counts": {key: int(used[key] - before[key]) for key in ("tomtom", "weather")},
            "reserved_units": float(used["units"] - before["units"]),
            "coordinates_submitted": coordinates,
            "cumulative": {key: float(value) for key, value in used.items()},
            "raw_bytes": len(raw),
            "gzip_bytes": len(gzip.compress(raw, compresslevel=9, mtime=0)),
            "point_count": heatmap.get("point_count"),
            "density": heatmap.get("density"),
            "frame_count": heatmap.get("frame_count"),
            "hazard_filters_included": heatmap.get("hazard_filters_included"),
            "recommendation_status": data.get("recommendation_status"),
            "warning_codes": [w["code"] for w in data.get("warnings", [])],
            "route_miles": [
                float(
                    Fraction(int(r["distance_m"]["numerator"]), int(r["distance_m"]["denominator"]))
                )
                / 1609.344
                for r in routes
            ],
        }
        print(json.dumps(record, allow_nan=False), flush=True)
    except Exception as error:
        print(
            json.dumps(
                {
                    "measurement_failure_type": type(error).__name__,
                    "cumulative": {k: float(v) for k, v in used.items()},
                }
            ),
            flush=True,
        )
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


if __name__ == "__main__":
    main()
