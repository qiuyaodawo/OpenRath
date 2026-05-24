"""Fixtures for the OpenViking-backed memory-plane tests.

All tests under ``tests/memory/backends/`` run against a real OpenViking
server (`scripts/launch_openviking.sh`). The autouse ``_openviking_canary``
fixture skips the entire module when:

- the ``openviking`` optional extra is not installed, OR
- ``$OPEN_VIKING_URL/health`` is unreachable, OR
- ``OPEN_VIKING_ROOT_API_KEY`` is unset (server is up but credentials are
  not exported in the shell — running a test without the key would fail
  the first auth check, which is noise, not a useful signal).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

_DEFAULT_URL = "http://127.0.0.1:1933"
_DEFAULT_CONF = Path.home() / ".openviking" / "ov.conf"


def _probe_health(url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=2.0) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return bool(body.get("healthy")), ""
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    except json.JSONDecodeError as exc:
        return False, f"non-JSON /health response: {exc}"


def _resolve_root_api_key() -> str | None:
    env_key = os.environ.get("OPEN_VIKING_ROOT_API_KEY")
    if env_key:
        return env_key
    if _DEFAULT_CONF.is_file():
        try:
            data = json.loads(_DEFAULT_CONF.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data.get("server", {}).get("root_api_key")
    return None


@pytest.fixture(scope="session")
def openviking_url() -> str:
    return os.environ.get("OPEN_VIKING_URL", _DEFAULT_URL)


@pytest.fixture(scope="session")
def openviking_root_api_key() -> str:
    key = _resolve_root_api_key()
    if not key:
        pytest.fail(
            "OPEN_VIKING_ROOT_API_KEY is not set and ~/.openviking/ov.conf could not be "
            "read; export the key printed by scripts/launch_openviking.sh."
        )
    return key


@pytest.fixture(autouse=True)
def _openviking_canary() -> Iterator[None]:
    pytest.importorskip("openviking", reason="openviking optional extra not installed")
    url = os.environ.get("OPEN_VIKING_URL", _DEFAULT_URL)
    healthy, detail = _probe_health(url)
    if not healthy:
        pytest.skip(
            f"OpenViking server unreachable at {url}/health ({detail}); start it with "
            "`bash scripts/launch_openviking.sh`."
        )
    if not _resolve_root_api_key():
        pytest.skip(
            "OpenViking server is up but OPEN_VIKING_ROOT_API_KEY is not set and "
            "~/.openviking/ov.conf has no server.root_api_key; export the key."
        )
    yield
