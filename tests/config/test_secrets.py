"""Real-fs tests for gitignore helpers and POSIX permission warning."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pytest

from rath.config.secrets import (
    chmod_user_only,
    ensure_config_dir_gitignore,
    ensure_project_gitignore_entry,
    warn_if_world_readable,
)


def test_ensure_config_dir_gitignore_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "openrath_dir"
    ensure_config_dir_gitignore(target)
    gi = target / ".gitignore"
    assert gi.is_file()
    body = gi.read_text(encoding="utf-8")
    assert "*" in body
    assert "!.gitignore" in body


def test_ensure_config_dir_gitignore_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "openrath_dir"
    ensure_config_dir_gitignore(target)
    custom_marker = "# custom user line\n*\n!.gitignore\n"
    (target / ".gitignore").write_text(custom_marker, encoding="utf-8")
    # Second call must not overwrite a user-edited file.
    ensure_config_dir_gitignore(target)
    assert (target / ".gitignore").read_text(encoding="utf-8") == custom_marker


def test_ensure_project_gitignore_appends_when_missing(tmp_path: Path) -> None:
    gi = tmp_path / ".gitignore"
    gi.write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    ensure_project_gitignore_entry(tmp_path)
    contents = gi.read_text(encoding="utf-8")
    assert "__pycache__/" in contents
    assert ".openrath/" in contents


def test_ensure_project_gitignore_does_not_duplicate(tmp_path: Path) -> None:
    gi = tmp_path / ".gitignore"
    gi.write_text(".openrath/\n", encoding="utf-8")
    ensure_project_gitignore_entry(tmp_path)
    contents = gi.read_text(encoding="utf-8")
    assert contents.count(".openrath/") == 1


def test_ensure_project_gitignore_matches_without_trailing_slash(
    tmp_path: Path,
) -> None:
    """Existing ``.openrath`` line (no slash) is recognized as a match."""
    gi = tmp_path / ".gitignore"
    gi.write_text(".openrath\n", encoding="utf-8")
    ensure_project_gitignore_entry(tmp_path)
    contents = gi.read_text(encoding="utf-8")
    # Existing variant kept; no new ".openrath/" line added.
    assert contents.count("openrath") == 1


def test_ensure_project_gitignore_skips_when_file_missing(tmp_path: Path) -> None:
    """No project .gitignore → no-op (don't create one)."""
    ensure_project_gitignore_entry(tmp_path)
    assert not (tmp_path / ".gitignore").exists()


def test_ensure_project_gitignore_handles_missing_trailing_newline(
    tmp_path: Path,
) -> None:
    gi = tmp_path / ".gitignore"
    gi.write_text("first-line", encoding="utf-8")  # no trailing newline
    ensure_project_gitignore_entry(tmp_path)
    contents = gi.read_text(encoding="utf-8")
    lines = contents.splitlines()
    assert lines == ["first-line", ".openrath/"]


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="chmod / stat permission bits are POSIX-only",
)
def test_chmod_user_only_sets_0600(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text("{}", encoding="utf-8")
    cfg.chmod(0o644)
    chmod_user_only(cfg)
    assert (cfg.stat().st_mode & 0o777) == 0o600


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="permission bits are POSIX-only",
)
def test_warn_if_world_readable_fires_on_loose_perms(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text("{}", encoding="utf-8")
    os.chmod(cfg, 0o644)
    # Reset module-level dedup state so this test sees a fresh warning.
    from rath.config import secrets as secrets_mod

    secrets_mod._WORLD_READABLE_WARNED.clear()
    with caplog.at_level(logging.WARNING, logger="rath.config.secrets"):
        warn_if_world_readable(cfg)
    assert any("permissions" in r.getMessage() for r in caplog.records)


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="permission bits are POSIX-only",
)
def test_warn_if_world_readable_silent_on_0600(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text("{}", encoding="utf-8")
    os.chmod(cfg, 0o600)
    from rath.config import secrets as secrets_mod

    secrets_mod._WORLD_READABLE_WARNED.clear()
    with caplog.at_level(logging.WARNING, logger="rath.config.secrets"):
        warn_if_world_readable(cfg)
    assert not any("permissions" in r.getMessage() for r in caplog.records)


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="permission bits are POSIX-only",
)
def test_warn_if_world_readable_dedupes_per_process(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text("{}", encoding="utf-8")
    os.chmod(cfg, 0o644)
    from rath.config import secrets as secrets_mod

    secrets_mod._WORLD_READABLE_WARNED.clear()
    with caplog.at_level(logging.WARNING, logger="rath.config.secrets"):
        warn_if_world_readable(cfg)
        warn_if_world_readable(cfg)
        warn_if_world_readable(cfg)
    warnings = [r for r in caplog.records if "permissions" in r.getMessage()]
    assert len(warnings) == 1
