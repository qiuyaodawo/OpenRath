"""Value-object semantics for every concrete :class:`~rath.backend.tool_types.BackendTool` payload."""

from __future__ import annotations

import dataclasses
import pickle

import pytest

import rath.backend as rb
from rath.backend.tool_types import (
    BackendTool,
    BackendToolCodeRun,
    BackendToolCommandRun,
    BackendToolFilesExists,
    BackendToolFilesList,
    BackendToolFilesRead,
    BackendToolFilesWrite,
)

_HASHABLE_CALLS = [
    BackendToolCommandRun(cmd=("ls",)),
    BackendToolCommandRun(cmd="ls -lah", timeout=5.0),
    BackendToolFilesRead(path="/etc/hostname"),
    BackendToolFilesRead(path="/x", encoding=None),
    BackendToolFilesWrite(path="/x", data=b"abc"),
    BackendToolFilesWrite(path="/x", data="abc", mode=0o600),
    BackendToolFilesList(path="/"),
    BackendToolFilesExists(path="/"),
    BackendToolCodeRun(code="print(1)"),
    BackendToolCodeRun(code="print(1)", language="python", timeout=2.0),
]


@pytest.mark.parametrize("call", _HASHABLE_CALLS)
def test_call_is_subclass_of_backend_tool(call: BackendTool) -> None:
    assert isinstance(call, BackendTool)


@pytest.mark.parametrize("call", _HASHABLE_CALLS)
def test_call_is_frozen(call: BackendTool) -> None:
    field_name = dataclasses.fields(call)[0].name
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(call, field_name, "should-fail")


@pytest.mark.parametrize("call", _HASHABLE_CALLS)
def test_call_pickle_round_trip(call: BackendTool) -> None:
    revived = pickle.loads(pickle.dumps(call))
    assert revived == call
    assert revived is not call


@pytest.mark.parametrize("call", _HASHABLE_CALLS)
def test_call_hash_stable(call: BackendTool) -> None:
    assert hash(call) == hash(call)


@pytest.mark.parametrize("call", _HASHABLE_CALLS)
def test_call_equals_self(call: BackendTool) -> None:
    assert call == call


def test_distinct_calls_inequal() -> None:
    assert BackendToolCommandRun(cmd=("a",)) != BackendToolCommandRun(cmd=("b",))
    assert BackendToolFilesRead(path="/a") != BackendToolFilesRead(path="/b")
    assert BackendToolFilesRead(path="/a") != BackendToolFilesExists(path="/a")


def test_command_run_defaults() -> None:
    c = BackendToolCommandRun(cmd="ls")
    assert c.env is None
    assert c.cwd is None
    assert c.stdin is None
    assert c.timeout is None


def test_files_read_text_default_encoding() -> None:
    assert BackendToolFilesRead(path="/x").encoding == "utf-8"


def test_files_write_default_mode() -> None:
    assert BackendToolFilesWrite(path="/x", data=b"").mode == 0o644


def test_code_run_default_language_is_python() -> None:
    assert BackendToolCodeRun(code="").language == "python"


def test_calls_have_slots() -> None:
    """frozen + slots is what gives us the value-object guarantee."""

    c = BackendToolCommandRun(cmd="ls")
    with pytest.raises(AttributeError):
        object.__setattr__(c, "brand_new_attr", "nope")


def test_calls_with_unhashable_field_remain_equal() -> None:
    a = BackendToolCommandRun(cmd="ls", env={"X": "1"})
    b = BackendToolCommandRun(cmd="ls", env={"X": "1"})
    assert a == b


def test_backend_reexports_same_tool_types() -> None:
    assert rb.BackendToolCommandRun is BackendToolCommandRun
    assert rb.BackendTool is BackendTool
