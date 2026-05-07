"""Agent: system :class:`~rath.session.session.Session` plus LLM prefs.

See :class:`~rath.llm.AgentLLMProvider`.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from rath.llm.agent_llm_provider import AgentLLMProvider
from rath.session.session import Session


@dataclass(slots=True)
class Agent:
    """System session plus LLM options for ``run_session_loop``."""

    agent_session: Session
    provider: AgentLLMProvider

    @property
    def data(self) -> Mapping[str, Any]:
        """Read-only mapping of underlying ``agent_session`` and ``provider``."""

        return MappingProxyType(
            {"agent_session": self.agent_session, "provider": self.provider}
        )

    def __repr__(self) -> str:
        prefs = self.provider
        extras = []
        if prefs.model is not None:
            extras.append(f"model={prefs.model!r}")
        if prefs.temperature is not None:
            extras.append(f"temperature={prefs.temperature!r}")
        if prefs.max_completion_tokens is not None:
            extras.append(f"max_completion_tokens={prefs.max_completion_tokens!r}")
        pref_s = ", ".join(extras) if extras else "defaults"
        return f"{type(self).__name__}(session_id={self.agent_session.id}, {pref_s})"


__all__ = ["Agent", "AgentLLMProvider"]
