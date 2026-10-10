"""Health must work without providers, authentication or a database."""

from django.test import Client, override_settings


@override_settings(ALLOWED_HOSTS=["testserver"])
def test_liveness() -> None:
    """A trivial real HTTP boundary test proves the backend pipeline."""
    response = Client().get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0", "check": "liveness"}
    assert response["Cache-Control"] == "no-store"


@override_settings(ALLOWED_HOSTS=["testserver"])
def test_configuration_readiness() -> None:
    """Readiness describes validated process config, not provider availability."""
    response = Client().get("/api/v1/health/?ready=1")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@override_settings(ALLOWED_HOSTS=["testserver"])
def test_health_rejects_post() -> None:
    """Unsupported methods return a safe API error."""
    response = Client().post("/api/v1/health/")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
