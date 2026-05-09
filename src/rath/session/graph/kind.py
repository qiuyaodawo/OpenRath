"""Lineage enums and lineage graph consistency errors."""

from __future__ import annotations

from enum import Enum


class LineageKind(str, Enum):
    """How a :class:`~rath.session.session.Session` entered the lineage DAG."""

    UNKNOWN = "unknown"
    LEAF_USER = "leaf_user"
    LEAF_SYSTEM = "leaf_system"
    OP_CREATE = "op_create"
    OP_SESSION_LOOP = "op_session_loop"
    OP_FORK = "op_fork"
    OP_DETACH = "op_detach"
    OP_MERGE = "op_merge"


class LineageConsistencyError(ValueError):
    """Raised when ``parent_session_ids`` reference missing nodes or form a cycle."""


__all__ = ["LineageKind", "LineageConsistencyError"]
