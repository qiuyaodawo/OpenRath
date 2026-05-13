"""Small shared helpers (paths + test env accessors)."""

from __future__ import annotations

from typing import Any

from rath.utils.env import project_root_with_pyproject
from rath.utils.decoding import decode_subprocess_output

__all__ = [
    "decode_subprocess_output",
    "project_root_with_pyproject",
    "TEST_BASE_URL",
    "TEST_API_KEY",
    "TEST_MODEL",
]


def __getattr__(name: str) -> Any:
    if name in ("TEST_BASE_URL", "TEST_API_KEY", "TEST_MODEL"):
        import rath.utils.env as _env

        return getattr(_env, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
