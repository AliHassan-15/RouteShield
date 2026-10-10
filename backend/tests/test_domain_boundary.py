"""The static boundary check detects both forms of framework imports."""

from tools.check_domain import main, violations


def test_domain_boundary() -> None:
    """Check the actual domain package."""
    main()


def test_boundary_detects_imports() -> None:
    """Prevent an accidentally ineffective checker."""
    assert violations("import django as framework\nfrom httpx import Client")
    assert violations("from providers.routing import route")
    assert not violations("from dataclasses import dataclass")
