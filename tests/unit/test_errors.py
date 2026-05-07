"""Tests for :mod:`rath.backend.errors`."""

from __future__ import annotations

import pickle

import pytest

from rath.backend import (
    BackendError,
    BackendNotFound,
    BackendSandboxClosed,
    BackendToolCommandRun,
    UnsupportedBackendTool,
)


def test_all_errors_inherit_from_backend_error() -> None:
    assert issubclass(UnsupportedBackendTool, BackendError)
    assert issubclass(BackendSandboxClosed, BackendError)
    assert issubclass(BackendNotFound, BackendError)


def test_unsupported_backend_tool_message_contains_names() -> None:
    err = UnsupportedBackendTool(BackendToolCommandRun, "weird")
    msg = str(err)
    assert "weird" in msg
    assert "BackendToolCommandRun" in msg
    assert err.call_type is BackendToolCommandRun
    assert err.backend_name == "weird"


def test_backend_sandbox_closed_carries_handle() -> None:
    err = BackendSandboxClosed("/tmp/abc")
    assert err.handle == "/tmp/abc"


def test_backend_not_found_lists_available() -> None:
    err = BackendNotFound("missing", ["local", "other"])
    assert err.name == "missing"
    assert err.available == ["local", "other"]
    msg = str(err)
    assert "missing" in msg
    assert "local" in msg


@pytest.mark.parametrize(
    "err",
    [
        UnsupportedBackendTool(BackendToolCommandRun, "x"),
        BackendSandboxClosed("/tmp/x"),
        BackendNotFound("x", ["a", "b"]),
    ],
)
def test_errors_are_picklable(err: BackendError) -> None:
    revived = pickle.loads(pickle.dumps(err))
    assert type(revived) is type(err)
    assert str(revived) == str(err)
