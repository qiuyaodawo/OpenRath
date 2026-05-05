"""Conformance: FlowToolCodeRun semantics across all backends."""

from __future__ import annotations

import pytest

from rath.backend import Backend, CodeResult, FlowToolCodeRun

pytestmark = pytest.mark.anyio


async def test_python_basic_print(backend: Backend) -> None:
    async with await backend.open() as sb:
        result = await sb.dispatch(FlowToolCodeRun(code="print(1 + 1)"))
        assert isinstance(result, CodeResult)
        assert b"2" in result.stdout
        assert result.error is None


async def test_python_runtime_error_populates_error(backend: Backend) -> None:
    async with await backend.open() as sb:
        result = await sb.dispatch(
            FlowToolCodeRun(code="raise ValueError('boom')")
        )
        assert isinstance(result, CodeResult)
        assert result.error is not None
        assert "ValueError" in result.error or "boom" in result.error


async def test_python_timeout_raises(backend: Backend) -> None:
    async with await backend.open() as sb:
        with pytest.raises(TimeoutError):
            await sb.dispatch(
                FlowToolCodeRun(code="import time; time.sleep(5)", timeout=0.5)
            )
