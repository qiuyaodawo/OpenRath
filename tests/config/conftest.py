"""Fixtures: isolate every config test to a tmp dir so ``~/.openrath/`` is never touched."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture(autouse=True)
def _isolate_openrath_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[Path]:
    """Pin ``OPENRATH_HOME`` to a per-test tmp directory.

    Every config test runs against a real filesystem location under
    ``tmp_path``; nothing in this suite touches the real user home. The
    fixture yields the path so tests that want to write/read directly
    don't have to re-resolve it.
    """
    target = tmp_path / "openrath_home"
    monkeypatch.setenv("OPENRATH_HOME", str(target))
    yield target
