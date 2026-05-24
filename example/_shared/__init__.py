"""Shared helpers for the OpenRath examples — the single source of truth.

Every numbered example imports from here instead of re-implementing provider
construction or streaming callbacks. Running ``python example/NN_*.py`` puts
``example/`` on ``sys.path`` (it is the script's directory), so ``import
_shared`` resolves without any path manipulation.
"""

from __future__ import annotations

from _shared.events import stream_to_stdout
from _shared.provider import provider_from_env

__all__ = ["provider_from_env", "stream_to_stdout"]
