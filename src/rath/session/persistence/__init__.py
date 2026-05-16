"""Append-only persistence for OpenRath sessions.

Stores each :class:`~rath.session.session.Session` as a JSONL file under
``.openrath/sessions/<uuid>.jsonl`` (resolved exactly like
``config.json`` — see :mod:`rath.config.paths`). Designed for crash safety:
every chunk is flushed to disk as it lands, so a ``kill -9`` mid-loop loses
at most the last partial line.

Public surface:

* :func:`persist_chunks` / :func:`compose_hooks` — write side, plug into
  ``run_session_loop(..., chunk_print=...)``.
* :func:`close_session_writers` — graceful trailer writeout.
* :func:`load_session` / :func:`list_persisted_sessions` — read side.
* :class:`PersistedSession` / :class:`PersistedSessionMeta` /
  :class:`PersistedSessionHeader` — round-trip dataclasses.
* :class:`SessionWriter` — direct writer for non-loop callers.
* :exc:`PersistenceError` — corrupt / unreadable file.
"""

from rath.session.persistence._migrations import (
    CURRENT_SCHEMA_VERSION,
    register_chunk_migration,
    register_header_migration,
)
from rath.session.persistence.errors import PersistenceError
from rath.session.persistence.hook import (
    close_session_writers,
    compose_hooks,
    persist_chunks,
)
from rath.session.persistence.loader import (
    PersistedSession,
    PersistedSessionHeader,
    PersistedSessionMeta,
    delete_session,
    list_persisted_sessions,
    load_session,
    prune_sessions,
)
from rath.session.persistence.paths import (
    SESSION_FILE_SUFFIX,
    SESSIONS_DIR_NAME,
    ensure_sessions_dir,
    session_file,
    sessions_dir,
)
from rath.session.persistence.writer import SessionWriter

__all__ = [
    # Errors
    "PersistenceError",
    # Hook helpers
    "persist_chunks",
    "compose_hooks",
    "close_session_writers",
    # Writer
    "SessionWriter",
    # Loader + GC
    "PersistedSession",
    "PersistedSessionHeader",
    "PersistedSessionMeta",
    "load_session",
    "list_persisted_sessions",
    "delete_session",
    "prune_sessions",
    # Migrations
    "CURRENT_SCHEMA_VERSION",
    "register_header_migration",
    "register_chunk_migration",
    # Paths
    "SESSIONS_DIR_NAME",
    "SESSION_FILE_SUFFIX",
    "sessions_dir",
    "session_file",
    "ensure_sessions_dir",
]
