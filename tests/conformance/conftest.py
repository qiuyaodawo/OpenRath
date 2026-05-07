"""Fixtures parametrizing ``local`` and ``opensandbox`` backends."""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator

import pytest

from rath.backend import Backend, get
from tests.conftest import opensandbox_real

_BACKEND_PARAMS = [
    pytest.param("local", id="local"),
    pytest.param(
        "opensandbox",
        id="opensandbox",
        marks=[opensandbox_real, pytest.mark.opensandbox],
    ),
]


@pytest.fixture(params=_BACKEND_PARAMS)
async def backend(request: pytest.FixtureRequest) -> AsyncIterator[Backend]:
    """Yield a fresh backend instance for each test."""
    bk = get(request.param)
    yield bk


@pytest.fixture
def python_cmd(backend: Backend) -> list[str]:
    """``[sys.executable]`` on local; ``["python3"]`` in OpenSandbox containers."""
    if backend.name == "local":
        return [sys.executable]
    return ["python3"]
