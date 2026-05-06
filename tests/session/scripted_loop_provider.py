"""In-process scripted LLM for ``run_session_loop`` tests (no ``unittest.mock``).

``complete`` returns a fixed sequence of :class:`~rath.llm.RathLLMChatResponse`
values. ``dispatch_tool`` forwards to the real sandbox so tool execution stays
honest (typically :class:`~rath.backend.adapters.local.LocalBackend`).
"""

from __future__ import annotations

from rath.backend import ToolResult
from rath.flow.tool import FlowToolCall, register_builtin_session_tools
from rath.flow.tool.tool_table import global_tool_table
from rath.llm import RathLLMChatRequest, RathLLMChatResponse, RathLLMFunctionTool
from rath.session.session import Session


class ScriptedSessionLoopProvider:
    """Pops scripted chat responses; dispatches tools on the live sandbox."""

    __slots__ = ("_queue",)

    def __init__(self, responses: list[RathLLMChatResponse]) -> None:
        self._queue = list(responses)
        register_builtin_session_tools()

    async def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse:
        if not self._queue:
            raise RuntimeError("scripted LLM queue empty")
        return self._queue.pop(0)

    async def dispatch_tool(
        self,
        session: Session,
        call: FlowToolCall,
    ) -> ToolResult | bool:
        return await session.require_sandbox().dispatch(call)

    def tool_schemas(self) -> tuple[RathLLMFunctionTool, ...]:
        return global_tool_table().schemas()
