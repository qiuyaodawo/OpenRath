"""Deterministic :func:`~rath.session.loop.run_session_loop` driver (queued responses, live sandbox)."""

from __future__ import annotations

from rath.backend import ToolResult
from rath.flow.tool import FlowToolCall, register_builtin_session_tools
from rath.flow.tool.tool_table import global_tool_table
from rath.llm import RathLLMChatRequest, RathLLMChatResponse, RathLLMFunctionTool
from rath.session.session import Session


class ScriptedSessionLoopExecutor:
    """Dequeues fixed :class:`~rath.llm.RathLLMChatResponse`; runs tools on ``session.require_sandbox()``."""

    __slots__ = ("_queue",)

    def __init__(self, responses: list[RathLLMChatResponse]) -> None:
        self._queue = list(responses)
        register_builtin_session_tools()

    def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse:
        if not self._queue:
            raise RuntimeError("scripted LLM queue empty")
        return self._queue.pop(0)

    def dispatch_tool(
        self,
        session: Session,
        call: FlowToolCall,
    ) -> ToolResult | bool:
        return session.require_sandbox().dispatch(call)

    def tool_schemas(self) -> tuple[RathLLMFunctionTool, ...]:
        return global_tool_table().schemas()
