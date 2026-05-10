"""Default SessionLoopExecutor: blocking LLM completions plus sandbox tool dispatch."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rath.flow.tool import FlowToolCall
from rath.llm import (
    RathLLMChatRequest,
    RathLLMChatResponse,
    RathLLMFunctionTool,
    RathOpenAIChatClient,
)
from rath.session.session import Session


class DefaultSessionLoopExecutor:
    """Default :class:`SessionLoopExecutor`: sync ``OpenAI`` client + sandbox ``dispatch``."""

    __slots__ = ("_client",)

    def __init__(self, client: RathOpenAIChatClient) -> None:
        self._client = client

    def tool_schemas(self) -> tuple[RathLLMFunctionTool, ...]:
        """Defer to :func:`~rath.session.loop.run_session_loop` loop-local tool table."""

        return ()

    def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse:
        """Call the synchronous :class:`~rath.llm.client.RathOpenAIChatClient`."""

        return self._client.complete(req)

    def dispatch_tool(
        self,
        session: Session,
        tool: FlowToolCall,
        arguments: Mapping[str, Any],
    ) -> Any:
        """Invoke ``tool(session, arguments)`` (sandbox or user-defined)."""

        return tool(session, dict(arguments or {}))


__all__ = ["DefaultSessionLoopExecutor"]
