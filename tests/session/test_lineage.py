"""Lineage graph: unit-level traversal/recording + JSONL export.

Consolidated from (every test function name preserved verbatim):
- test_lineage_graph_unit.py    (graph/kind/recording/traverse unit tests)
- test_lineage_export.py        (JSONL exporter)
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

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
from rath.session.graph.kind import LineageConsistencyError
from rath.session.graph.recording import (
    session_graph_mode,
    session_graph_mode_override,
)
from rath.session.graph.traverse import (
    ancestors_bfs,
    edge_pairs,
    validate_acyclic,
)
from rath.session.manager import session_registry

# ---------------------------------------------------------------------------
# graph unit tests
# ---------------------------------------------------------------------------


def _sess(parents: tuple[uuid.UUID, ...]) -> Session:
    s = Session.from_user_message("_")
    s.parent_session_ids = parents
    s.lineage_kind = LineageKind.OP_FORK
    return s


def test_validate_acyclic_rejects_missing_parent() -> None:
    a_id, b_id = uuid.uuid4(), uuid.uuid4()
    a = Session.from_user_message("_")
    a.id = a_id
    a.parent_session_ids = ()

    b = Session.from_user_message("_")
    b.id = b_id
    b.parent_session_ids = (a_id, uuid.uuid4())

    with pytest.raises(LineageConsistencyError):
        validate_acyclic({a_id: a, b_id: b})


def test_validate_acyclic_rejects_cycle() -> None:
    uid = uuid.uuid4()
    a = Session.from_user_message("_")
    a.id = uid
    a.parent_session_ids = (uid,)
    with pytest.raises(LineageConsistencyError):
        validate_acyclic({uid: a})


def test_ancestors_bfs_order_linear() -> None:
    c_id, b_id, a_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    a = Session.from_user_message("_")
    a.id = a_id
    a.parent_session_ids = ()
    b = Session.from_user_message("_")
    b.id = b_id
    b.parent_session_ids = (a_id,)
    c = Session.from_user_message("_")
    c.id = c_id
    c.parent_session_ids = (b_id,)
    by_id = {a_id: a, b_id: b, c_id: c}
    validate_acyclic(by_id)
    assert ancestors_bfs(by_id, c_id) == (b_id, a_id)


def test_edge_pairs() -> None:
    a_id, b_id = uuid.uuid4(), uuid.uuid4()
    b = _sess((a_id,))
    b.id = b_id
    a = _sess(())
    a.id = a_id
    assert set(edge_pairs({a_id: a, b_id: b})) == {(a_id, b_id)}


def test_lineage_recorder_respects_mode_off() -> None:
    s = Session.from_user_message("x")
    pid = uuid.uuid4()
    with session_graph_mode_override(False):
        LineageRecorder.stamp_new_session(
            s,
            parent_session_ids=(pid,),
            lineage_operator="t",
            lineage_kind=LineageKind.OP_FORK,
        )
    assert s.parent_session_ids == ()
    assert session_graph_mode() is True


def test_lineage_recorder_stamps_when_on() -> None:
    s = Session.from_user_message("x")
    p = uuid.uuid4()
    LineageRecorder.stamp_new_session(
        s,
        parent_session_ids=(p,),
        lineage_operator="run_session_loop",
        lineage_kind=LineageKind.OP_SESSION_LOOP,
        lineage_extras=(("k", 1),),
    )
    assert s.parent_session_ids == (p,)
    assert s.lineage_operator == "run_session_loop"
    assert s.lineage_kind == LineageKind.OP_SESSION_LOOP
    assert s.lineage_extras == (("k", 1),)


def test_lineage_journal_yields_readable_after_exit() -> None:
    """``lineage_journal_tracking`` must yield a journal whose ``visit_order``
    contains every session created inside the block, and remain readable
    after the context manager exits."""
    with lineage_journal_tracking() as journal:
        a = Session.from_user_message("alpha")
        LineageRecorder.stamp_new_session(
            a,
            parent_session_ids=(),
            lineage_operator="test",
            lineage_kind=LineageKind.LEAF_USER,
        )
        forked = a.fork()  # stamp via Session.fork
        del forked

    assert len(journal.visit_order) == 2
    assert journal.visit_order[0] == a.id


def test_lineage_journal_external_journal_is_mutated_in_place() -> None:
    """Passing in a journal must reuse it: caller-owned reference sees updates."""
    j = LineageJournal()
    with lineage_journal_tracking(journal=j) as yielded:
        assert yielded is j
        s = Session.from_user_message("x")
        LineageRecorder.stamp_new_session(
            s,
            parent_session_ids=(),
            lineage_operator="t",
            lineage_kind=LineageKind.LEAF_USER,
        )

    assert j.visit_order == [s.id]


# ---------------------------------------------------------------------------
# JSONL export
# ---------------------------------------------------------------------------


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
    rows = [json.loads(ln) for ln in out.read_text(encoding="utf-8").splitlines() if ln]
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
