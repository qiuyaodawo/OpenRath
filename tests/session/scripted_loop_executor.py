"""Deterministic :func:`~rath.session.loop.run_session_loop` driver (queued responses)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rath.flow.tool import FlowToolCall
from rath.llm import RathLLMChatRequest, RathLLMChatResponse, RathLLMFunctionTool
from rath.session.session import Session


class ScriptedSessionLoopExecutor:
    """Dequeues fixed :class:`~rath.llm.RathLLMChatResponse`; runs ``FlowToolCall``."""

    __slots__ = ("_queue",)

    def __init__(self, responses: list[RathLLMChatResponse]) -> None:
        self._queue = list(responses)

    def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse:
        if not self._queue:
            raise RuntimeError("scripted LLM queue empty")
        return self._queue.pop(0)

    def dispatch_tool(
        self,
        session: Session,
        tool: FlowToolCall,
        arguments: Mapping[str, Any],
    ) -> Any:
        return tool(session, dict(arguments or {}))

    def tool_schemas(self) -> tuple[RathLLMFunctionTool, ...]:
        return ()
