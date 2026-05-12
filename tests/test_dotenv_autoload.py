"""Auto-load of a project ``.env`` from :mod:`rath.__init__`."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from rath import _load_project_dotenv


def test_loads_env_from_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A ``.env`` in the current working directory is picked up."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "RATH_TEST_AUTOLOAD_KEY=loaded-from-dotenv\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("RATH_TEST_AUTOLOAD_KEY", raising=False)
    monkeypatch.delenv("RATH_SKIP_DOTENV", raising=False)

    _load_project_dotenv()

    assert os.environ.get("RATH_TEST_AUTOLOAD_KEY") == "loaded-from-dotenv"


def test_does_not_override_process_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Process env wins over ``.env`` (.env fills gaps, not overrides)."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "RATH_TEST_AUTOLOAD_KEY=from-dotenv\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RATH_TEST_AUTOLOAD_KEY", "from-process")
    monkeypatch.delenv("RATH_SKIP_DOTENV", raising=False)

    _load_project_dotenv()

    assert os.environ.get("RATH_TEST_AUTOLOAD_KEY") == "from-process"


def test_skip_env_disables_autoload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``RATH_SKIP_DOTENV=1`` must bypass loading entirely."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "RATH_TEST_AUTOLOAD_KEY=should-not-load\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("RATH_TEST_AUTOLOAD_KEY", raising=False)
    monkeypatch.setenv("RATH_SKIP_DOTENV", "1")

    _load_project_dotenv()

    assert "RATH_TEST_AUTOLOAD_KEY" not in os.environ
