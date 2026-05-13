"""Repository path helpers and test-only environment accessors.

The attributes ``TEST_BASE_URL``, ``TEST_API_KEY``, and ``TEST_MODEL`` are
resolved lazily from environment variables of the same names (empty or
whitespace-only values become ``None``). Intended for pytest and harnesses —
production code should use :class:`~rath.llm.provider.Provider` explicitly.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

__all__ = [
    "project_root_with_pyproject",
    "TEST_BASE_URL",
    "TEST_API_KEY",
    "TEST_MODEL",
]


def project_root_with_pyproject() -> Path:
    """Repository root: parent of ``src`` that contains ``pyproject.toml``."""
    return Path(__file__).resolve().parents[3]


def _test_env_value(key: str) -> str | None:
    raw = os.environ.get(key, "").strip()
    return raw if raw else None


def __getattr__(name: str) -> Any:
    if name == "TEST_BASE_URL":
        return _test_env_value("TEST_BASE_URL")
    if name == "TEST_API_KEY":
        return _test_env_value("TEST_API_KEY")
    if name == "TEST_MODEL":
        return _test_env_value("TEST_MODEL")
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}",
    )


def __dir__() -> list[str]:
    return sorted(__all__)


if TYPE_CHECKING:
    TEST_BASE_URL: str | None
    TEST_API_KEY: str | None
    TEST_MODEL: str | None
