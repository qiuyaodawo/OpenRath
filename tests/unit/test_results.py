"""Value-object semantics for every concrete :class:`ToolResult` subclass."""

from __future__ import annotations

import dataclasses
import pickle

import pytest

from rath.backend import (
    CodeResult,
    CommandResult,
    FileContent,
    FileEntries,
    FileEntry,
    FileWriteResult,
    ToolExecutionFailure,
    ToolResult,
)

_RESULTS: list[ToolResult] = [
    ToolExecutionFailure(kind="k", message="m", detail="d"),
    CommandResult(exit_code=0, stdout=b"hi", stderr=b"", elapsed_ms=1.0),
    FileContent(data=b"hello"),
    FileContent(data="hello"),
    FileEntries(
        entries=(
            FileEntry(name="a", path="/a", is_dir=False),
            FileEntry(name="b", path="/b", is_dir=True),
        )
    ),
    FileWriteResult(bytes_written=42),
    CodeResult(text=None, stdout=b"out", stderr=b"", error=None),
    CodeResult(text="42", stdout=b"", stderr=b"", error="oops"),
]


@pytest.mark.parametrize("res", _RESULTS)
def test_result_is_frozen(res: ToolResult) -> None:
    field_name = dataclasses.fields(res)[0].name
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(res, field_name, "should-fail")


@pytest.mark.parametrize("res", _RESULTS)
def test_result_pickle_round_trip(res: ToolResult) -> None:
    revived = pickle.loads(pickle.dumps(res))
    assert revived == res
    assert revived is not res
    assert hash(revived) == hash(res)


def test_file_entries_distinct_content_inequal() -> None:
    a = FileEntries(entries=(FileEntry(name="a", path="/a", is_dir=False),))
    b = FileEntries(entries=(FileEntry(name="b", path="/b", is_dir=False),))
    assert a != b


def test_file_entry_is_value_object() -> None:
    e = FileEntry(name="x", path="/x", is_dir=False)
    assert pickle.loads(pickle.dumps(e)) == e
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(e, "name", "y")
