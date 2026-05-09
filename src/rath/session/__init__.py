"""Session package: chunks, sandbox loop, registry, lineage graph, and primitives."""

from rath.session.chunk import (
    ChunkKind,
    ChunkRow,
    ChunkTable,
    assistant_turn_chunk,
    chunk_table_to_messages,
    system_text_chunk,
    tool_feedback_chunk,
    user_text_chunk,
)
from rath.session.graph import (
    LineageConsistencyError,
    LineageJournal,
    LineageKind,
    LineageRecorder,
    SessionLineage,
    ancestors_bfs,
    descendants_dfs_preorder,
    edge_pairs,
    lineage_journal_optional,
    lineage_journal_tracking,
    lineage_view_dataclass,
    session_graph_mode,
    session_graph_mode_override,
    validate_acyclic,
)
from rath.session.manager import SessionRegistry, session_registry
from rath.session.loop import SessionLoopExecutor, run_session_loop
from rath.session.primitives import (
    create_leaf_system,
    create_leaf_user,
    detach_session,
    fork_session,
    merge_sessions,
)
from rath.session.provider_builtin import DefaultSessionLoopExecutor
from rath.session.session import Session


__all__ = [
    "ancestors_bfs",
    "assistant_turn_chunk",
    "chunk_table_to_messages",
    "ChunkKind",
    "ChunkRow",
    "ChunkTable",
    "create_leaf_system",
    "create_leaf_user",
    "DefaultSessionLoopExecutor",
    "descendants_dfs_preorder",
    "detach_session",
    "edge_pairs",
    "fork_session",
    "LineageConsistencyError",
    "LineageJournal",
    "lineage_journal_optional",
    "lineage_journal_tracking",
    "LineageKind",
    "LineageRecorder",
    "lineage_view_dataclass",
    "merge_sessions",
    "session_graph_mode",
    "session_graph_mode_override",
    "Session",
    "SessionLineage",
    "SessionLoopExecutor",
    "SessionRegistry",
    "run_session_loop",
    "session_registry",
    "system_text_chunk",
    "tool_feedback_chunk",
    "user_text_chunk",
    "validate_acyclic",
]
