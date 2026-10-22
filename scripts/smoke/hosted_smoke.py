"""Opt-in hosted checks; stdlib only, no credentials, no analysis unless requested."""

import argparse
import gzip
import json
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class SmokeFailure(ValueError):
    """Only these fixed local labels may be printed on failure."""


def base_url(value: str) -> str:
    """Require credential-free HTTPS, with HTTP permitted only on loopback for offline tests."""
    parsed = urlsplit(value)
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.scheme not in ({"http", "https"} if local else {"https"})
    ):
        raise SmokeFailure("Use a credential-free HTTPS base URL (HTTP only on loopback).")
    return value.rstrip("/") + "/"


def origin(value: str) -> str:
    parts = urlsplit(value)
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


class Assets(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.paths: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        path = (
            values.get("src") if tag == "script" else values.get("href") if tag == "link" else None
        )
        if path and (
            tag == "script" or values.get("rel") in {"stylesheet", "modulepreload", "preload"}
        ):
            self.paths.add(path)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


def request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> tuple[int, dict[str, str], bytes, int]:
    """Never print transport exceptions, URL strings, bodies or headers."""
    req = Request(url, data=body, method=method, headers=headers or {})
    try:
        response = build_opener(NoRedirect()).open(req, timeout=40)
    except HTTPError as error:
        response = error
    with response:
        wire = response.read(10_000_001)
        if len(wire) > 10_000_000:
            raise SmokeFailure("Response exceeds smoke-check size limit.")
        metadata = {k.lower(): v for k, v in response.headers.items()}
        raw = gzip.decompress(wire) if metadata.get("content-encoding") == "gzip" else wire
        return response.status, metadata, raw, len(wire)


def require(condition: object, label: str) -> None:
    if not condition:
        raise SmokeFailure(label)
    print("PASS " + label)


def error_shape(raw: bytes, headers: dict[str, str]) -> bool:
    body = json.loads(raw)
    error = body.get("error", {})
    return (
        isinstance(error.get("code"), str)
        and isinstance(error.get("message"), str)
        and isinstance(error.get("details"), dict)
        and bool(re.fullmatch(r"[A-Za-z0-9-]{1,80}", headers.get("x-request-id", "")))
    )


def smoke(backend: str, frontend: str, analysis: bool = False, local_proxy: bool = False) -> None:
    """Exercise public validation without calling a provider in the default run."""
    backend, frontend = base_url(backend), base_url(frontend)
    if local_proxy and any(
        urlsplit(v).hostname not in {"localhost", "127.0.0.1", "::1"} for v in (backend, frontend)
    ):
        raise SmokeFailure("--local-proxy is limited to loopback servers.")
    api = (
        backend if urlsplit(backend).path.rstrip("/") == "/api/v1" else urljoin(backend, "api/v1/")
    )
    front_origin = origin(frontend)
    proxy = {"X-Forwarded-Proto": "https"} if local_proxy else {}
    for suffix, check, expected in [
        ("health/", "liveness", "ok"),
        ("health/?ready=1", "readiness", "ready"),
    ]:
        status, headers, raw, _ = request(api + suffix, headers=proxy)
        body = json.loads(raw)
        require(
            status == 200
            and body.get("status") == expected
            and body.get("check") == check
            and isinstance(body.get("version"), str),
            check,
        )
        require(
            headers.get("x-content-type-options") == "nosniff"
            and headers.get("x-frame-options") == "DENY"
            and headers.get("referrer-policy") == "no-referrer"
            and "max-age=" in headers.get("strict-transport-security", ""),
            "backend security headers: " + check,
        )
    status, headers, _, _ = request(
        api + "route-analysis/",
        "OPTIONS",
        {
            **proxy,
            "Origin": front_origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    require(
        status == 200
        and headers.get("access-control-allow-origin") == front_origin
        and "POST" in headers.get("access-control-allow-methods", "")
        and "content-type" in headers.get("access-control-allow-headers", "").lower(),
        "allowed CORS preflight",
    )
    _, headers, _, _ = request(api + "health/", headers={**proxy, "Origin": front_origin})
    require(
        headers.get("access-control-allow-origin") == front_origin, "allowed simple CORS request"
    )
    for method in ["GET", "OPTIONS"]:
        _, headers, _, _ = request(
            api + "health/",
            method,
            {
                **proxy,
                "Origin": "https://disallowed.example.test",
                "Access-Control-Request-Method": "POST",
            },
        )
        require("access-control-allow-origin" not in headers, "disallowed CORS " + method)
    for suffix, method, data in [
        ("geocode/?q=ab", "GET", None),
        ("route-analysis/", "POST", b"{}"),
    ]:
        status, headers, raw, _ = request(
            api + suffix, method, {**proxy, "Content-Type": "application/json"}, data
        )
        require(
            status == 400 and error_shape(raw, headers),
            "validation envelope and request ID: " + method,
        )
    status, headers, raw, _ = request(frontend)
    require(
        status == 200
        and "text/html" in headers.get("content-type", "")
        and "no-cache" in headers.get("cache-control", ""),
        "frontend HTML and shell caching",
    )
    policy = headers.get("content-security-policy", "")
    require(
        "script-src 'self';" in policy
        and "frame-ancestors 'none'" in policy
        and "worker-src 'self' blob:" in policy
        and "https://tiles.openfreemap.org" in policy
        and "unsafe-eval" not in policy
        and (local_proxy or origin(backend) in policy),
        "frontend CSP",
    )
    require(
        headers.get("x-content-type-options") == "nosniff"
        and headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        and "camera=()" in headers.get("permissions-policy", "")
        and headers.get("x-frame-options") == "DENY",
        "frontend security headers",
    )
    assets = Assets()
    assets.feed(raw.decode("utf-8"))
    require(bool(assets.paths), "built asset references exist")
    for path in sorted(assets.paths):
        target = urljoin(frontend, path)
        require(origin(target) == front_origin, "asset remains on frontend origin")
        status, headers, _, _ = request(target)
        suffix = urlsplit(target).path.rsplit(".", 1)[-1]
        mime = {"js": ("javascript",), "css": ("text/css",), "woff2": ("font/woff2",)}.get(
            suffix, ()
        )
        require(
            status == 200
            and bool(mime)
            and any(t in headers.get("content-type", "") for t in mime),
            "asset response and MIME: " + suffix,
        )
        if "/assets/" in urlsplit(target).path:
            require("immutable" in headers.get("cache-control", ""), "hashed asset caching")
    for label, target in [("backend", api + "health/"), ("frontend", frontend)]:
        if local_proxy and label == "frontend":
            print("SKIP frontend HTTP-to-HTTPS: Vite preview has no TLS/edge redirect")
            continue
        parts = urlsplit(target)
        status, headers, _, _ = request(urlunsplit(("http", parts.netloc, parts.path, "", "")))
        location = urlsplit(headers.get("location", ""))
        require(
            status in {301, 302, 307, 308}
            and location.scheme == "https"
            and location.hostname == parts.hostname,
            label + " HTTP-to-HTTPS redirect",
        )
    if analysis:
        # Exactly one POST, no retry. Coordinates copied from EXAMPLE_TRIPS.
        payload = {
            "origin": {"label": "Santa Monica Pier", "latitude": 34.0094, "longitude": -118.4973},
            "destination": {
                "label": "Los Angeles City Hall",
                "latitude": 34.0537,
                "longitude": -118.2428,
            },
            "departure_time": (datetime.now(UTC) + timedelta(hours=3)).isoformat(),
            "departure_timezone": "UTC",
            "load_weight_lb": 45000,
        }
        started = time.perf_counter()
        status, _, raw, wire = request(
            api + "route-analysis/",
            "POST",
            {**proxy, "Content-Type": "application/json", "Accept-Encoding": "gzip"},
            json.dumps(payload).encode(),
        )
        elapsed = time.perf_counter() - started
        body = json.loads(raw)
        require(
            status == 200
            and body.get("route_count") == 3
            and len(body.get("routes", [])) == 3
            and body.get("recommendation_status")
            in {
                "RECOMMENDED",
                "BEST_FULLY_ASSESSED_AVAILABLE",
                "ALL_BLOCKED",
                "NO_FULLY_ASSESSED_TRAVELABLE_ROUTE",
                "ALL_INCOMPLETE",
            }
            and isinstance(body.get("heatmap"), dict)
            and body["heatmap"].get("frame_count") == 49,
            "one live Santa Monica analysis",
        )
        print(
            json.dumps(
                {
                    "wall_seconds": round(elapsed, 3),
                    "wire_bytes": wire,
                    "raw_bytes": len(raw),
                    "computed_gzip_bytes": len(gzip.compress(raw, mtime=0)),
                    "analysis_requests": 1,
                }
            )
        )
    else:
        print("SKIP live analysis: --analysis was not supplied; zero provider requests expected")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backend")
    parser.add_argument("frontend")
    parser.add_argument("--analysis", action="store_true")
    parser.add_argument(
        "--local-proxy",
        action="store_true",
        help="Offline only: emulate Render TLS termination on loopback",
    )
    args = parser.parse_args()
    try:
        smoke(args.backend, args.frontend, args.analysis, args.local_proxy)
    except Exception as error:
        print("FAIL " + (str(error) if isinstance(error, SmokeFailure) else type(error).__name__))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
