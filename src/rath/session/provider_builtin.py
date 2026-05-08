"""Default SessionLoopExecutor: blocking LLM completions plus sandbox tool dispatch."""

from __future__ import annotations

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


class DefaultSessionLoopExecutor:
    """Default :class:`SessionLoopExecutor`: sync ``OpenAI`` client + sandbox ``dispatch``."""

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
        """Register built-in session tools and return OpenAI function schemas."""

        register_builtin_session_tools(self._table)
        return self._table.schemas()

    @property
    def tool_table(self) -> ToolTable:
        return self._table

    def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse:
        """Call the synchronous :class:`~rath.llm.client.RathOpenAIChatClient`."""

        return self._client.complete(req)

    def dispatch_tool(
        self,
        session: Session,
        call: FlowToolCall,
    ) -> ToolResult | bool:
        """Run ``call`` on ``session``'s sandbox."""

        return session.require_sandbox().dispatch(call)


__all__ = ["DefaultSessionLoopExecutor"]
