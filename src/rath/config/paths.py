"""Resolve where ``config.json`` lives on disk.

Three-tier precedence — first hit wins:

1. ``OPENRATH_HOME`` environment variable (explicit override; tilde expanded).
2. ``./.openrath/`` directory in :func:`Path.cwd` (project-local marker).
3. ``~/.openrath/`` (user-level default).

Pure functions: no side-effects beyond reading the env and CWD; no directory
creation. ``ConfigStore.save`` handles the ``mkdir`` when writing.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    "OPENRATH_HOME_ENV",
    "CONFIG_FILENAME",
    "PROJECT_MARKER_DIR",
    "USER_DIR_NAME",
    "resolve_config_dir",
    "resolve_config_path",
    "is_project_local",
]

OPENRATH_HOME_ENV = "OPENRATH_HOME"
CONFIG_FILENAME = "config.json"
PROJECT_MARKER_DIR = ".openrath"
USER_DIR_NAME = ".openrath"


def resolve_config_dir() -> Path:
    """Return the directory that holds ``config.json``.

    Raises :class:`FileNotFoundError` only when ``OPENRATH_HOME`` is set but
    points at a non-directory path that already exists (e.g. a regular file).
    A missing target is fine — the caller will create it on first save.
    """
    env_value = os.environ.get(OPENRATH_HOME_ENV, "").strip()
    if env_value:
        path = Path(env_value).expanduser().resolve()
        if path.exists() and not path.is_dir():
            raise FileNotFoundError(
                f"{OPENRATH_HOME_ENV}={env_value!r} exists but is not a directory",
            )
        return path
    cwd_local = Path.cwd() / PROJECT_MARKER_DIR
    if cwd_local.is_dir():
        return cwd_local.resolve()
    return Path.home() / USER_DIR_NAME


def resolve_config_path() -> Path:
    """Return the full path to ``config.json`` under the resolved config dir."""
    return resolve_config_dir() / CONFIG_FILENAME


def is_project_local(config_dir: Path) -> bool:
    """Return whether ``config_dir`` is the project-local ``./.openrath/``.

    Used by :mod:`rath.config.secrets` to decide whether to also append
    ``.openrath/`` to the surrounding project's ``.gitignore`` on save.
    """
    try:
        return config_dir.resolve() == (Path.cwd() / PROJECT_MARKER_DIR).resolve()
    except (OSError, RuntimeError):
        return False
