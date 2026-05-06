"""OpenRath: torch-like workflows with sandbox backends and LLM clients.

:mod:`rath.backend` loads eagerly. :mod:`rath.flow` stays a shallow namespace so
tool imports avoid pulling session code. Access :mod:`rath.session` via
``from rath.session import ...`` (lazy-loaded as ``rath.session`` attribute).
"""

from __future__ import annotations

from typing import Any

from rath import backend
from rath import flow

__all__ = ["backend", "flow", "session"]


def __getattr__(name: str) -> Any:
    if name == "session":
        from rath import session as _session

        return _session
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
