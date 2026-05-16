"""Cross-process advisory write lock for a single :class:`SessionWriter`.

Two processes that open the same ``<sessions>/<id>.jsonl`` file with
:class:`SessionWriter` would otherwise interleave their lines, producing a
file that can't be deterministically parsed back. This helper acquires an
**exclusive, non-blocking** advisory lock on the open file descriptor —
the second writer fails fast with :exc:`PersistenceError` rather than
silently corrupting the stream.

POSIX uses :func:`fcntl.flock` (kernel releases on fd close). Windows uses
:func:`msvcrt.locking` against the first byte; the file region is unlocked
when the fd closes (or when :meth:`release` is invoked explicitly).
"""

from __future__ import annotations

import sys
from typing import IO

from rath.session.persistence.errors import PersistenceError

__all__ = ["FileLock"]


class FileLock:
    """Acquire an exclusive non-blocking lock on a file descriptor."""

    __slots__ = ("_fp", "_acquired")

    def __init__(self, fp: IO[str]) -> None:
        self._fp = fp
        self._acquired = False

    def acquire(self) -> None:
        """Take the lock or raise :exc:`PersistenceError` if already held."""
        if self._acquired:
            return
        try:
            self._platform_acquire()
        except OSError as e:
            raise PersistenceError(
                f"another process is already writing to {self._fp.name!r}; "
                f"refusing to interleave appends",
            ) from e
        self._acquired = True

    def release(self) -> None:
        """Release the lock if held. Safe to call on a closed fd (no-op)."""
        if not self._acquired:
            return
        try:
            self._platform_release()
        except OSError:  # pragma: no cover -- racing fs / closed fd
            pass
        self._acquired = False

    # --- platform ------------------------------------------------------------

    def _platform_acquire(self) -> None:
        if sys.platform.startswith("win"):
            import msvcrt  # type: ignore[import-not-found, unused-ignore]

            # Lock the first byte non-blocking. msvcrt.locking operates from
            # the current file pointer; save / restore around the call so
            # we don't disturb the append cursor.
            saved = self._fp.tell()
            try:
                self._fp.seek(0)
                msvcrt.locking(self._fp.fileno(), msvcrt.LK_NBLCK, 1)
            finally:
                self._fp.seek(saved)
        else:
            import fcntl

            fcntl.flock(self._fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _platform_release(self) -> None:
        if sys.platform.startswith("win"):
            import msvcrt  # type: ignore[import-not-found, unused-ignore]

            saved = self._fp.tell()
            try:
                self._fp.seek(0)
                msvcrt.locking(self._fp.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                self._fp.seek(saved)
        else:
            import fcntl

            fcntl.flock(self._fp.fileno(), fcntl.LOCK_UN)
