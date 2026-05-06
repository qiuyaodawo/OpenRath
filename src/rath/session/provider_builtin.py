"""Default SessionLoopProvider: thread-backed LLM plus async sandbox dispatch."""

from __future__ import annotations

import anyio

from rath.backend import ToolResult
from rath.flow.tool import (
    FlowToolCall,
    ToolTable,
    global_tool_table,
    register_builtin_session_tools,
)
from rath.llm import (
    RathLLMChatRequest,
    RathLLMChatResponse,
    RathLLMFunctionTool,
    RathOpenAIChatClient,
)
from rath.session.session import Session


class DefaultSessionLoopProvider:
    """Wires :class:`RathOpenAIChatClient` and :class:`ToolTable` into the loop."""

    __slots__ = ("_client", "_table")

    def __init__(
        self,
        client: RathOpenAIChatClient,
        *,
        tool_table: ToolTable | None = None,
    ) -> None:
        self._client = client
        self._table = tool_table or global_tool_table()

    def tool_schemas(self) -> tuple[RathLLMFunctionTool, ...]:
        register_builtin_session_tools(self._table)
        return self._table.schemas()

    @property
    def tool_table(self) -> ToolTable:
        return self._table

    async def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse:
        return await anyio.to_thread.run_sync(self._client.complete, req)

    async def dispatch_tool(
        self,
        session: Session,
        call: FlowToolCall,
    ) -> ToolResult | bool:
        return await session.require_sandbox().dispatch(call)


__all__ = ["DefaultSessionLoopProvider"]
