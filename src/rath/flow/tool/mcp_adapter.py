"""Bridge an MCP stdio server into the :class:`FlowToolCall` interface.

Lets OpenRath use any tool exposed by a Model Context Protocol server as if
it were a built-in :class:`~rath.flow.tool.FlowToolCall`. Only the **stdio**
transport is supported in this module; SSE / HTTP transports can be added
later without changing the public surface.

Install the optional extra::

    pip install "openrath[mcp]"

Minimal use::

    from rath.flow.tool.mcp_adapter import mcp_tools_from_server

    tools = mcp_tools_from_server(["python", "-m", "mcp_server_filesystem"])
    agent = flow.Agent("Use mcp tools", Provider(model="gpt-5.5"), tools=list(tools))

The implementation opens a fresh stdio subprocess for each ``list_tools``
and each ``call_tool``. That keeps the lifecycle trivially correct under
anyio's cancellation scopes; per-call cost is dominated by LLM latency
in typical workflows. A long-lived session worker is a possible later
optimization.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any, cast

from rath.backend.dedicated_loop import DedicatedEventLoopThread
from rath.flow.tool.base import FlowToolCall
from rath.session.session import Session

try:
    from mcp import (  # type: ignore[import-not-found, unused-ignore]
        ClientSession,
        StdioServerParameters,
    )
    from mcp.client.stdio import (  # type: ignore[import-not-found, unused-ignore]
        stdio_client,
    )

    _MCP_AVAILABLE = True
except ImportError:  # pragma: no cover -- optional extra
    _MCP_AVAILABLE = False


__all__ = [
    "MCPClient",
    "MCPToolCall",
    "mcp_tools_from_server",
    "shared_mcp_loop",
    "is_mcp_available",
]


def is_mcp_available() -> bool:
    """Return whether the ``mcp`` package is importable."""
    return _MCP_AVAILABLE


_MCP_LOOP: DedicatedEventLoopThread | None = None
_MCP_LOOP_LOCK = threading.Lock()


def shared_mcp_loop() -> DedicatedEventLoopThread:
    """Process-wide dedicated asyncio loop used by :class:`MCPClient`."""

    global _MCP_LOOP
    with _MCP_LOOP_LOCK:
        if _MCP_LOOP is None:
            _MCP_LOOP = DedicatedEventLoopThread()
        return _MCP_LOOP


class MCPClient:
    """Sync wrapper around an MCP stdio server.

    Each :meth:`list_tools` and :meth:`call_tool` opens a fresh subprocess on
    the shared MCP loop. Construct with a list-of-string command (e.g.
    ``["python", "-m", "mcp_server_filesystem"]``) or with positional command
    + args::

        client = MCPClient("python", args=["-m", "mcp_server_filesystem"])
        for t in client.list_tools():
            print(t.name)
    """

    def __init__(
        self,
        command: str | list[str],
        *,
        args: list[str] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        if not _MCP_AVAILABLE:  # pragma: no cover -- gated by is_mcp_available()
            raise RuntimeError(
                "mcp is not installed; install with `pip install openrath[mcp]`",
            )
        if isinstance(command, list):
            cmd_exe = command[0]
            cmd_args = list(command[1:])
        else:
            cmd_exe = command
            cmd_args = list(args or [])
        self._params = StdioServerParameters(
            command=cmd_exe,
            args=cmd_args,
            env=dict(env) if env is not None else None,
        )
        self._loop = shared_mcp_loop()

    def list_tools(self) -> list[Any]:
        """Connect to the server and return its ``tools`` list (mcp.types.Tool)."""

        async def _do() -> list[Any]:
            async with stdio_client(self._params) as (r, w):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    res = await session.list_tools()
                    return list(res.tools)

        return self._loop.run(_do())

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> Any:
        """Connect to the server and run ``name`` with ``arguments``.

        Returns the raw ``CallToolResult`` from the SDK; the caller decides how
        to surface :attr:`CallToolResult.content` (typically a list of text or
        image content parts).
        """

        async def _do() -> Any:
            async with stdio_client(self._params) as (r, w):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    return await session.call_tool(name, arguments=dict(arguments))

        return self._loop.run(_do())


def _coerce_input_schema(input_schema: Any) -> Mapping[str, Any]:
    """Normalize the MCP ``inputSchema`` field to a JSON-schema dict.

    The mcp Python SDK historically returned dict or pydantic models for this
    field. Best-effort: prefer ``model_dump`` if available, otherwise fall
    back to ``dict()`` cast.
    """
    if hasattr(input_schema, "model_dump"):
        return cast(Mapping[str, Any], input_schema.model_dump(mode="json"))
    if isinstance(input_schema, dict):
        return dict(input_schema)
    if input_schema is None:
        return {"type": "object", "properties": {}}
    return dict(input_schema)


def _flatten_call_result(result: Any) -> Any:
    """Reduce a CallToolResult to something the session loop can JSON-encode.

    If the result has a ``content`` list with text parts, concatenate their
    ``text`` attributes; otherwise return ``result`` as-is and let the loop's
    own summarizer handle it.
    """
    content = getattr(result, "content", None)
    if not content:
        return getattr(result, "structuredContent", None) or {"ok": True}
    parts: list[str] = []
    for c in content:
        text = getattr(c, "text", None)
        if isinstance(text, str):
            parts.append(text)
    if parts:
        return {"text": "\n".join(parts)}
    return {"content": [str(c) for c in content]}


class MCPToolCall(FlowToolCall):
    """Wraps one tool from an :class:`MCPClient` as a :class:`FlowToolCall`."""

    def __init__(
        self,
        *,
        client: MCPClient,
        name: str,
        description: str | None,
        parameters: Mapping[str, Any],
    ) -> None:
        self._client = client
        self._name = name
        self._description = description
        self._parameters = parameters

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str | None:
        return self._description

    @property
    def parameters(self) -> Mapping[str, Any]:
        return self._parameters

    def __call__(self, session: Session, arguments: Mapping[str, Any]) -> Any:
        del session  # MCP tools don't get the OpenRath session
        result = self._client.call_tool(self._name, arguments)
        return _flatten_call_result(result)


def mcp_tools_from_server(
    command: str | list[str],
    *,
    args: list[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[MCPToolCall, ...]:
    """Connect to a stdio MCP server, list its tools, return wrapped FlowToolCalls.

    The returned :class:`MCPToolCall` instances all share one
    :class:`MCPClient`, so subsequent invocations of any tool reuse the same
    stdio command for fresh subprocesses. The caller is responsible for
    keeping a reference to the returned tuple as long as those tools are in
    use; there is no explicit close because each call already opens / closes
    its own subprocess.
    """
    client = MCPClient(command, args=args, env=env)
    raw_tools = client.list_tools()
    return tuple(
        MCPToolCall(
            client=client,
            name=str(t.name),
            description=getattr(t, "description", None),
            parameters=_coerce_input_schema(getattr(t, "inputSchema", None)),
        )
        for t in raw_tools
    )
