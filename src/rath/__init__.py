"""OpenRath: sandbox backends, LLM clients, and composable flow.

Sandbox dispatch uses :class:`~rath.backend.tool_types.BackendTool`. The session loop
uses :class:`~rath.flow.tool.FlowToolCall` as the flow-layer tool abstraction.

Import submodules explicitly, e.g. ``rath.flow.agent_param``; ``rath.session`` is
lazy-loaded via :func:`__getattr__`.

On import this module looks for a ``.env`` file in the current working
directory (and ancestor directories) via :func:`dotenv.find_dotenv` and loads
it without overriding values already set in ``os.environ``. Disable by setting
``RATH_SKIP_DOTENV=1`` before import.
"""

from __future__ import annotations

import os
from typing import Any


def _load_project_dotenv() -> None:
    """Best-effort: populate :mod:`os.environ` from a project ``.env``.

    Honors ``RATH_SKIP_DOTENV`` for environments where library-side env
    mutation is undesirable. Uses ``override=False`` so values already set
    in the process environment win, which matches the documented
    "``.env`` first, then process env vars" precedence in the install guide.
    """

    if os.environ.get("RATH_SKIP_DOTENV", "").strip():
        return
    try:
        from dotenv import find_dotenv, load_dotenv
    except ImportError:  # pragma: no cover -- python-dotenv is a core dep
        return
    path = find_dotenv(usecwd=True)
    if path:
        load_dotenv(path, override=False)


_load_project_dotenv()


from rath import backend  # noqa: E402  (load after dotenv so backends see env)
from rath import flow  # noqa: E402

__all__ = ["backend", "flow", "session"]


def __getattr__(name: str) -> Any:
    """Lazy-load ``session`` on first attribute access."""
    if name == "session":
        from rath import session as _session

        return _session
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
