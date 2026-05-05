"""Conformance fixture: parametrize over every available backend.

The ``opensandbox`` parameter is gated on ``opensandbox_real`` (defined in
the top-level ``tests/conftest.py``), which skips when no local
``opensandbox-server`` is reachable on ``localhost:8080``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from rath.backend import Backend, get
from tests.conftest import opensandbox_real

_BACKEND_PARAMS = [
    pytest.param("local", id="local"),
    pytest.param("opensandbox", id="opensandbox", marks=opensandbox_real),
]


@pytest.fixture(params=_BACKEND_PARAMS)
async def backend(request: pytest.FixtureRequest) -> AsyncIterator[Backend]:
    """Yield a fresh backend instance for each test."""
    bk = get(request.param)
    yield bk
