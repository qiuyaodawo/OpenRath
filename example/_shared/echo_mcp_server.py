"""Tiny stdio MCP server used by ``example/06_mcp_tool.py``.

Exposes one ``echo`` tool. Not a serious deployment — the point is to give
the MCP bridge example something deterministic to talk to with no external
dependencies.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server: Server = Server("rath-demo-echo")


@server.list_tools()
async def _list_tools() -> list[Tool]:
    return [
        Tool(
            name="echo",
            description="Echo the provided text back to the caller.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to echo",
                    },
                },
                "required": ["text"],
            },
        ),
    ]


@server.call_tool()
async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "echo":
        return [TextContent(type="text", text=str(arguments.get("text", "")))]
    return [TextContent(type="text", text=f"unknown tool: {name}")]


async def _main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(_main())
