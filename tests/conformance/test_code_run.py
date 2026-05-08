"""``BackendToolCodeRun`` results per backend."""

from __future__ import annotations

import pytest

from rath.backend import Backend, CodeResult, BackendToolCodeRun


def test_python_basic_print(backend: Backend) -> None:
    with backend.open() as sb:
        result = sb.dispatch(BackendToolCodeRun(code="print(1 + 1)"))
        assert isinstance(result, CodeResult)
        assert b"2" in result.stdout
        assert result.error is None


def test_python_runtime_error_populates_error(backend: Backend) -> None:
    with backend.open() as sb:
        result = sb.dispatch(BackendToolCodeRun(code="raise ValueError('boom')"))
        assert isinstance(result, CodeResult)
        assert result.error is not None
        assert "ValueError" in result.error or "boom" in result.error


def test_python_timeout_raises(backend: Backend) -> None:
    with backend.open() as sb:
        with pytest.raises(TimeoutError):
            sb.dispatch(
                BackendToolCodeRun(code="import time; time.sleep(5)", timeout=0.5)
            )
