"""Session lineage DAG helpers (recording, traversal, legacy DTO).

No ``SessionGraph`` / ``SessionNode`` / ``SessionEdge`` types: edges are derived from
:attr:`~rath.session.session.Session.parent_session_ids` (implicit graph, torch-like).
"""

from __future__ import annotations

from rath.session.graph.kind import LineageConsistencyError, LineageKind
from rath.session.graph.legacy import SessionLineage
from rath.session.graph.recording import (
    LineageJournal,
    LineageRecorder,
    lineage_journal_optional,
    lineage_journal_tracking,
    session_graph_mode,
    session_graph_mode_override,
)
from rath.session.graph.traverse import (
    FrozenLineageView,
    ancestors_bfs,
    descendants_dfs_preorder,
    edge_pairs,
    lineage_view_dataclass,
    validate_acyclic,
)

__all__ = [
    "FrozenLineageView",
    "LineageConsistencyError",
    "LineageJournal",
    "LineageKind",
    "LineageRecorder",
    "SessionLineage",
    "ancestors_bfs",
    "descendants_dfs_preorder",
    "edge_pairs",
    "lineage_journal_optional",
    "lineage_journal_tracking",
    "lineage_view_dataclass",
    "session_graph_mode",
    "session_graph_mode_override",
    "validate_acyclic",
]
