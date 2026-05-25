"""pytest root: asyncio anyio backend, OpenSandbox TCP gate, marker-based timeouts."""

from __future__ import annotations

import os
import socket

import pytest

# Per-marker timeout overrides. The global default lives in pytest.ini
# (``timeout = 30``); slow paths (live backends, real LLM, full-stack
# integration, perf benchmarks) need more headroom. Anything not listed here
# inherits the 30 s default.
_MARKER_TIMEOUT_S: dict[str, int] = {
    "opensandbox": 300,
    "opensandbox_real": 300,
    "openviking": 300,
    "live_llm": 180,
    "integration": 600,
    "bench": 600,
}


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Boost ``@pytest.mark.timeout`` for slow-path markers."""
    for item in items:
        if item.get_closest_marker("timeout") is not None:
            continue
        boost = 0
        for name, secs in _MARKER_TIMEOUT_S.items():
            if item.get_closest_marker(name) is not None and secs > boost:
                boost = secs
        if boost:
            item.add_marker(pytest.mark.timeout(boost))


@pytest.fixture
def anyio_backend() -> str:
    """Force AnyIO pytest plugin to asyncio."""
    return "asyncio"


def _opensandbox_server_running(host: str = "localhost", port: int = 8080) -> bool:
    """Returns whether TCP ``host:port`` accepts connections (gates OpenSandbox tests)."""
    target_host = os.environ.get("OPENSANDBOX_TEST_HOST", host)
    target_port = int(os.environ.get("OPENSANDBOX_TEST_PORT", str(port)))
    try:
        with socket.create_connection((target_host, target_port), timeout=0.5):
            return True
    except OSError:
        return False


opensandbox_real = pytest.mark.skipif(
    not _opensandbox_server_running(),
    reason=(
        "opensandbox-server is not running on localhost:8080; "
        "start it with e.g. `OPENSANDBOX_INSECURE_SERVER=YES uvx opensandbox-server`"
    ),
)
