"""Unit tests for :mod:`rath.session.graph` (no LLM / no sandbox)."""

from __future__ import annotations

import uuid

import pytest

from rath.session.graph.kind import LineageConsistencyError, LineageKind
from rath.session.graph.recording import (
    LineageRecorder,
    session_graph_mode,
    session_graph_mode_override,
)
from rath.session.graph.traverse import (
    ancestors_bfs,
    edge_pairs,
    validate_acyclic,
)
from rath.session.session import Session


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
