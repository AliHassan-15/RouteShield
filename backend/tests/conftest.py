"""Normal tests are offline; only the explicitly enabled two-request smoke uses sockets."""

import os
import socket
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def prohibit_network(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Block connection/DNS entry points, including third-party HTTP clients."""
    if (
        request.node.name == "test_tomtom_live_smoke"
        and os.environ.get("ROUTESHIELD_LIVE_TOMTOM") == "1"
    ):
        yield
        return

    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("Network access is forbidden in the normal test suite.")

    for name in ("connect", "connect_ex", "sendto", "sendmsg"):
        if hasattr(socket.socket, name):
            monkeypatch.setattr(socket.socket, name, blocked)
    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    yield
