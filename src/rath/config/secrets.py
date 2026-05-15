"""Defensive measures for the on-disk config:

1. Auto-write a ``.gitignore`` inside the config directory that refuses to
   stage anything except itself — so a project-local ``./.openrath/`` cannot
   accidentally leak ``config.json`` to commit history.
2. When the project-local mode is used, append ``.openrath/`` to the
   surrounding project's ``.gitignore`` (if present and missing the line).
3. On POSIX, warn once per process if ``config.json`` is group- or
   world-readable (mode bits ``0o077``).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

__all__ = [
    "ensure_config_dir_gitignore",
    "ensure_project_gitignore_entry",
    "warn_if_world_readable",
]

logger = logging.getLogger(__name__)

# Deny-all with explicit allowlist for the gitignore itself. The example
# template is whitelisted so users can commit a sanitized copy if they want.
_GITIGNORE_BODY = "*\n!.gitignore\n!config.json.example\n"


def ensure_config_dir_gitignore(config_dir: Path) -> None:
    """Write ``config_dir/.gitignore`` if absent. Idempotent."""
    config_dir.mkdir(parents=True, exist_ok=True)
    gitignore = config_dir / ".gitignore"
    if gitignore.exists():
        return
    gitignore.write_text(_GITIGNORE_BODY, encoding="utf-8")


def ensure_project_gitignore_entry(
    project_root: Path, marker: str = ".openrath/"
) -> None:
    """Append ``marker`` to ``<project_root>/.gitignore`` if needed.

    Skips when:
    - the project ``.gitignore`` does not exist (nothing to amend), or
    - ``marker`` already appears as its own line (any trailing whitespace
      stripped before comparison).
    """
    gitignore = project_root / ".gitignore"
    if not gitignore.is_file():
        return
    try:
        existing = gitignore.read_text(encoding="utf-8")
    except OSError:  # pragma: no cover -- racing fs / perms
        return
    needle = marker.rstrip("/")
    for line in existing.splitlines():
        if line.strip().rstrip("/") == needle:
            return
    suffix = "" if existing.endswith("\n") else "\n"
    gitignore.write_text(f"{existing}{suffix}{marker}\n", encoding="utf-8")


_WORLD_READABLE_WARNED: set[Path] = set()


def warn_if_world_readable(path: Path) -> None:
    """POSIX-only: warn once per process per path when group/other bits are set."""
    if sys.platform.startswith("win"):
        return
    if not path.is_file():
        return
    try:
        mode = path.stat().st_mode
    except OSError:  # pragma: no cover -- racing fs
        return
    if (mode & 0o077) == 0:
        return
    resolved = path.resolve()
    if resolved in _WORLD_READABLE_WARNED:
        return
    _WORLD_READABLE_WARNED.add(resolved)
    logger.warning(
        "rath.config: %s has permissions %o; "
        "secrets may be readable by other users. "
        "Run: chmod 600 %s",
        resolved,
        mode & 0o777,
        resolved,
    )


def chmod_user_only(path: Path) -> None:
    """Restrict ``path`` to ``0600`` on POSIX. No-op on Windows."""
    if sys.platform.startswith("win"):
        return
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover -- racing fs / unsupported
        pass
