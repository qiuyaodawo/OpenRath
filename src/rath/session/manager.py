"""In-process registry for :class:`~rath.session.Session` debugging hooks."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from uuid import UUID

from rath.session.session import Session


@dataclass
class SessionRegistry:
    """Tracks known sessions and the active session id for debugging."""

    _by_id: dict[UUID, Session] = field(default_factory=dict)
    _active_id: UUID | None = None
    _lock: Lock = field(default_factory=Lock)

    def register(self, session: Session) -> None:
        with self._lock:
            self._by_id[session.id] = session

    def get(self, session_id: UUID) -> Session | None:
        with self._lock:
            return self._by_id.get(session_id)

    def set_active(self, session: Session | None) -> None:
        with self._lock:
            self._active_id = None if session is None else session.id

    def get_active_id(self) -> UUID | None:
        with self._lock:
            return self._active_id


_GLOBAL = SessionRegistry()


def session_registry() -> SessionRegistry:
    return _GLOBAL


__all__ = ["SessionRegistry", "session_registry"]
