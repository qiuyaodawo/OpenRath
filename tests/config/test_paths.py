"""Real-filesystem tests for path resolution.

No mocks. Every test sets up real directories under ``tmp_path`` and
exercises :func:`resolve_config_dir` / :func:`resolve_config_path` against
them, plus a real chdir to test the project-local marker fallback.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rath.config.paths import (
    CONFIG_FILENAME,
    PROJECT_MARKER_DIR,
    is_project_local,
    resolve_config_dir,
    resolve_config_path,
)


def test_env_var_explicit_path_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "explicit"
    target.mkdir()
    monkeypatch.setenv("OPENRATH_HOME", str(target))
    assert resolve_config_dir() == target.resolve()
    assert resolve_config_path() == target.resolve() / CONFIG_FILENAME


def test_env_var_missing_directory_is_returned_without_create(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "not-yet-existing"
    monkeypatch.setenv("OPENRATH_HOME", str(target))
    resolved = resolve_config_dir()
    assert resolved == target.resolve()
    assert not resolved.exists()


def test_env_var_pointing_at_regular_file_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sneaky = tmp_path / "actually-a-file"
    sneaky.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("OPENRATH_HOME", str(sneaky))
    with pytest.raises(FileNotFoundError, match="not a directory"):
        resolve_config_dir()


def test_tilde_expansion_in_env_var(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Repoint HOME to the tmp dir so ~ expands somewhere safe, then make
    # OPENRATH_HOME reference HOME via a literal tilde.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows
    monkeypatch.setenv("OPENRATH_HOME", "~/cfg")
    resolved = resolve_config_dir()
    assert resolved == (tmp_path / "cfg").resolve()


def test_project_local_marker_wins_when_env_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENRATH_HOME", raising=False)
    project = tmp_path / "project"
    (project / PROJECT_MARKER_DIR).mkdir(parents=True)
    monkeypatch.chdir(project)
    assert resolve_config_dir() == (project / PROJECT_MARKER_DIR).resolve()


def test_falls_back_to_user_home_when_neither_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENRATH_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows
    monkeypatch.chdir(tmp_path)  # CWD has no .openrath/ marker
    assert resolve_config_dir() == tmp_path / ".openrath"


def test_is_project_local_true_for_cwd_marker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / PROJECT_MARKER_DIR).mkdir()
    monkeypatch.chdir(tmp_path)
    assert is_project_local(tmp_path / PROJECT_MARKER_DIR) is True


def test_is_project_local_false_for_env_var_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    external = tmp_path / "elsewhere"
    external.mkdir()
    assert is_project_local(external) is False
