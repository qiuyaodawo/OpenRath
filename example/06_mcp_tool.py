"""06 · MCP tools — borrow tools from a Model Context Protocol server.

`mcp_tools_from_server` launches an MCP stdio server and exposes each of its
tools as a `FlowToolCall`, so they drop straight into `flow.Agent(tools=...)`
alongside your own. This example talks to the tiny in-repo echo server, so no
external setup is needed; swap the command for a real server such as
``["python", "-m", "mcp_server_filesystem"]`` for a useful deployment.

Run:
    python example/06_mcp_tool.py

No LLM key required — it discovers and calls the MCP tool directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

from rath.flow.tool.mcp_adapter import mcp_tools_from_server
from rath.session import Session

_ECHO_SERVER = Path(__file__).parent / "_shared" / "echo_mcp_server.py"


def main() -> None:
    tools = mcp_tools_from_server([sys.executable, str(_ECHO_SERVER)])
    print(f"Discovered {len(tools)} MCP tool(s):")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description}")
        print(f"    parameters keys: {list(tool.parameters.keys())}")

    if not tools:
        return

    echo = next((t for t in tools if t.name == "echo"), tools[0])
    # MCP tools ignore the session argument; pass a throwaway one.
    result = echo(Session.from_user_message("unused"), {"text": "hello from mcp"})
    print("\nresult:", result)


if __name__ == "__main__":
    main()
