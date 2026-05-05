"""Top-level pytest configuration shared by all test layers."""

from __future__ import annotations

import os
import socket

import pytest

from rath.utils.env import default_env_file_path, load_dotenv_if_present


# Load project .env once (never override existing process env). Ensures
# OPEN_SANDBOX_* and OPENSANDBOX_* match ``opensandbox`` SDK / server helpers.
load_dotenv_if_present(default_env_file_path(), override=False)


@pytest.fixture
def anyio_backend() -> str:
    """Pin async tests to asyncio; trio coverage is out of scope for now."""
    return "asyncio"


def _opensandbox_server_running(host: str = "localhost", port: int = 8080) -> bool:
    """Probe whether a local ``opensandbox-server`` is reachable.

    Test-only helper: never used at runtime, only to decide whether the
    OpenSandbox-related tests should run or be skipped.
    """
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
