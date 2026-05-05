"""Value-object semantics for every concrete :class:`FlowToolCall` subclass."""

from __future__ import annotations

import dataclasses
import pickle

import pytest

from rath.flow.tool import (
    FlowToolCall,
    FlowToolCodeRun,
    FlowToolCommandRun,
    FlowToolFilesExists,
    FlowToolFilesList,
    FlowToolFilesRead,
    FlowToolFilesWrite,
)

_HASHABLE_CALLS = [
    FlowToolCommandRun(cmd=("ls",)),
    FlowToolCommandRun(cmd="ls -lah", timeout=5.0),
    FlowToolFilesRead(path="/etc/hostname"),
    FlowToolFilesRead(path="/x", encoding=None),
    FlowToolFilesWrite(path="/x", data=b"abc"),
    FlowToolFilesWrite(path="/x", data="abc", mode=0o600),
    FlowToolFilesList(path="/"),
    FlowToolFilesExists(path="/"),
    FlowToolCodeRun(code="print(1)"),
    FlowToolCodeRun(code="print(1)", language="python", timeout=2.0),
]


@pytest.mark.parametrize("call", _HASHABLE_CALLS)
def test_call_is_subclass_of_flow_tool_call(call: FlowToolCall) -> None:
    assert isinstance(call, FlowToolCall)


@pytest.mark.parametrize("call", _HASHABLE_CALLS)
def test_call_is_frozen(call: FlowToolCall) -> None:
    field_name = dataclasses.fields(call)[0].name
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(call, field_name, "should-fail")


@pytest.mark.parametrize("call", _HASHABLE_CALLS)
def test_call_pickle_round_trip(call: FlowToolCall) -> None:
    revived = pickle.loads(pickle.dumps(call))
    assert revived == call
    assert revived is not call


@pytest.mark.parametrize("call", _HASHABLE_CALLS)
def test_call_hash_stable(call: FlowToolCall) -> None:
    assert hash(call) == hash(call)


@pytest.mark.parametrize("call", _HASHABLE_CALLS)
def test_call_equals_self(call: FlowToolCall) -> None:
    assert call == call


def test_distinct_calls_inequal() -> None:
    assert FlowToolCommandRun(cmd=("a",)) != FlowToolCommandRun(cmd=("b",))
    assert FlowToolFilesRead(path="/a") != FlowToolFilesRead(path="/b")
    assert FlowToolFilesRead(path="/a") != FlowToolFilesExists(path="/a")


def test_command_run_defaults() -> None:
    c = FlowToolCommandRun(cmd="ls")
    assert c.env is None
    assert c.cwd is None
    assert c.stdin is None
    assert c.timeout is None


def test_files_read_text_default_encoding() -> None:
    assert FlowToolFilesRead(path="/x").encoding == "utf-8"


def test_files_write_default_mode() -> None:
    assert FlowToolFilesWrite(path="/x", data=b"").mode == 0o644


def test_code_run_default_language_is_python() -> None:
    assert FlowToolCodeRun(code="").language == "python"


def test_calls_have_slots() -> None:
    """frozen + slots is what gives us the value-object guarantee.

    With ``slots=True`` adding a new attribute raises ``AttributeError`` even
    via :func:`object.__setattr__` (which bypasses the frozen check).
    """
    c = FlowToolCommandRun(cmd="ls")
    with pytest.raises(AttributeError):
        object.__setattr__(c, "brand_new_attr", "nope")


def test_calls_with_unhashable_field_remain_equal() -> None:
    """A dict env is unhashable but ``==`` still works as expected."""
    a = FlowToolCommandRun(cmd="ls", env={"X": "1"})
    b = FlowToolCommandRun(cmd="ls", env={"X": "1"})
    assert a == b


def test_backend_reexports_same_flow_tool_types() -> None:
    import rath.backend as rb

    assert rb.FlowToolCommandRun is FlowToolCommandRun
    assert rb.FlowToolCall is FlowToolCall
