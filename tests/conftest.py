"""pytest root: preload ``.env``, asyncio anyio backend, OpenSandbox TCP gate."""

from __future__ import annotations

import os
import socket

import pytest

from rath.utils.env import default_env_file_path, load_dotenv_if_present

load_dotenv_if_present(default_env_file_path(), override=False)


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
