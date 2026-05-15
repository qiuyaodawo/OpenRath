"""Wire an MCP stdio server's tools into a session loop.

Run::

    python example/mcp_tool_usage.py

This example launches a tiny in-process MCP server (``_demo_echo_server``) so
no external setup is needed; replace the ``command`` argument with a real
server such as ``["python", "-m", "mcp_server_filesystem"]`` for a useful
deployment.
"""

from __future__ import annotations

import sys
from pathlib import Path

from rath.flow.tool.mcp_adapter import mcp_tools_from_server

_DEMO_SERVER = Path(__file__).parent / "_demo_echo_server.py"


def main() -> None:
    tools = mcp_tools_from_server([sys.executable, str(_DEMO_SERVER)])
    print(f"Discovered {len(tools)} MCP tool(s):")
    for t in tools:
        print(f"  - {t.name}: {t.description}")
        print(f"    parameters keys: {list(t.parameters.keys())}")

    # Use one of the tools through the FlowToolCall interface.
    if tools:
        echo = next((t for t in tools if t.name == "echo"), tools[0])
        # The first arg (session) is unused by MCP tools; pass None-equivalent.
        from rath.session import Session

        result = echo(Session.from_user_message("dummy"), {"text": "hello from mcp"})
        print("\nresult:", result)


if __name__ == "__main__":
    main()
