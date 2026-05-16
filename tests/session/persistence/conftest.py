"""Isolate every persistence test to a tmp ``OPENRATH_HOME`` directory."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture(autouse=True)
def _isolate_openrath_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[Path]:
    """Pin ``OPENRATH_HOME`` to a per-test tmp directory.

    All session persistence reads/writes resolve under this directory, so
    the real ``~/.openrath/`` is never touched.
    """
    target = tmp_path / "openrath_home"
    monkeypatch.setenv("OPENRATH_HOME", str(target))
    yield target
