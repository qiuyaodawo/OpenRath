"""JSONL lineage exporter (:mod:`rath.session.graph.export`)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from rath.session import Session
from rath.session.graph import (
    LineageJournal,
    LineageKind,
    LineageRecorder,
    export_journal_jsonl,
    export_jsonl,
    export_jsonl_string,
    lineage_journal_tracking,
    session_to_jsonl_row,
)
from rath.session.manager import session_registry


def _stamped(parents: tuple[uuid.UUID, ...]) -> Session:
    s = Session.from_user_message("x")
    LineageRecorder.stamp_new_session(
        s,
        parent_session_ids=parents,
        lineage_operator="t",
        lineage_kind=LineageKind.OP_FORK,
        lineage_extras=(("trace", "demo"),),
    )
    return s


def test_session_to_jsonl_row_has_expected_keys() -> None:
    p = uuid.uuid4()
    s = _stamped((p,))
    row = session_to_jsonl_row(s)
    assert row["id"] == str(s.id)
    assert row["parent_session_ids"] == [str(p)]
    assert row["lineage_operator"] == "t"
    assert row["lineage_kind"] == LineageKind.OP_FORK.value
    assert row["lineage_extras"] == [["trace", "demo"]]
    assert row["chunk_count"] == 1
    assert row["cumulative_usage"] is None


def test_export_jsonl_string_roundtrip() -> None:
    a = _stamped(())
    b = _stamped((a.id,))
    text = export_jsonl_string([a, b])
    assert text.endswith("\n")
    lines = [ln for ln in text.split("\n") if ln]
    assert len(lines) == 2
    parsed = [json.loads(ln) for ln in lines]
    assert parsed[0]["id"] == str(a.id)
    assert parsed[1]["parent_session_ids"] == [str(a.id)]


def test_export_jsonl_writes_file(tmp_path: Path) -> None:
    a = _stamped(())
    out = tmp_path / "nested" / "lineage.jsonl"
    export_jsonl([a], out)
    assert out.is_file()
    assert json.loads(out.read_text(encoding="utf-8").strip())["id"] == str(a.id)


def test_export_journal_jsonl_via_registry(tmp_path: Path) -> None:
    """Journal collects visited ids; exporter resolves them via the registry."""
    reg = session_registry()
    with lineage_journal_tracking() as journal:
        a = _stamped(())
        b = _stamped((a.id,))
        reg.register(a)
        reg.register(b)

    out = tmp_path / "graph.jsonl"
    export_journal_jsonl(journal, out)
    rows = [
        json.loads(ln)
        for ln in out.read_text(encoding="utf-8").splitlines()
        if ln
    ]
    # journal.visit_order order should be preserved
    assert [r["id"] for r in rows] == [str(uid) for uid in journal.visit_order]


def test_export_journal_jsonl_skip_unknown(tmp_path: Path) -> None:
    """Sessions not in the registry are silently skipped by default."""
    j = LineageJournal(visit_order=[uuid.uuid4(), uuid.uuid4()])
    out = tmp_path / "graph.jsonl"
    export_journal_jsonl(j, out)
    assert out.read_text(encoding="utf-8") == ""


def test_lineage_extras_coerces_non_jsonable_values() -> None:
    """Non-JSON values in lineage_extras must not break the export."""
    s = Session.from_user_message("x")
    # Use a non-serializable extras value (a set) - exporter should coerce.
    LineageRecorder.stamp_new_session(
        s,
        parent_session_ids=(),
        lineage_operator="t",
        lineage_kind=LineageKind.LEAF_USER,
        lineage_extras=(("weird", {1, 2}),),
    )
    text = export_jsonl_string([s])
    row = json.loads(text.strip())
    # value coerced to str representation
    assert isinstance(row["lineage_extras"][0][1], str)
