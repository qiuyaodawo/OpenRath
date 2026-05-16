"""Errors raised by :mod:`rath.session.persistence`."""

from __future__ import annotations

__all__ = ["PersistenceError"]


class PersistenceError(RuntimeError):
    """Raised when a persisted session file is corrupt or unreadable.

    The string carries a human-readable summary including the file path and,
    where available, the byte offset / line number of the failure. The
    original :class:`json.JSONDecodeError` or :class:`OSError` is chained via
    :attr:`__cause__`.
    """
