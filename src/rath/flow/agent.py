"""Agent: system :class:`~rath.session.session.Session` plus :class:`AgentLLMProvider` options."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from rath.session.session import Session


@dataclass(frozen=True, kw_only=True, slots=True)
class AgentLLMProvider:
    """LLM routing and sampling options for :func:`~rath.session.loop.run_session_loop`.

    Mirrors OpenAI-compat completion kwargs carried by :class:`~rath.llm.RathLLMChatRequest`
    **except** ``messages`` and ``tools`` (the loop fills those). Optional ``model`` selects
    a concrete endpoint model id when not ``None``; secrets stay on the executor client.
    """

    model: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_completion_tokens: int | None = None
    max_tokens: int | None = None
    stop: str | list[str] | None = None
    n: int | None = None
    seed: int | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    tool_choice: Any | None = None
    parallel_tool_calls: bool | None = None
    response_format: dict[str, Any] | None = None
    logit_bias: dict[str, int] | None = None
    logprobs: bool | None = None
    top_logprobs: int | None = None
    reasoning_effort: str | None = None
    verbosity: str | None = None
    metadata: dict[str, str] | None = None
    user: str | None = None
    store: bool | None = None
    service_tier: str | None = None
    extra_create_args: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )


@dataclass(slots=True)
class Agent:
    """System session and LLM preferences passed to :func:`~rath.session.loop.run_session_loop`."""

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
