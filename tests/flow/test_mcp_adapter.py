"""MCP stdio adapter tests.

``mcp`` is now a core dependency, so the full subprocess round-trip via
the in-tree ``example/_demo_echo_server.py`` runs unconditionally.
"""

from __future__ import annotations

import sys
from pathlib import Path

from rath.flow.tool.mcp_adapter import (
    _coerce_input_schema,
    _flatten_call_result,
)

_DEMO_SERVER = Path(__file__).resolve().parents[2] / "example" / "_demo_echo_server.py"


def test_coerce_input_schema_passes_dict_through() -> None:
    schema = {"type": "object", "properties": {"x": {"type": "string"}}}
    assert _coerce_input_schema(schema) == schema


def test_coerce_input_schema_handles_none() -> None:
    assert _coerce_input_schema(None) == {"type": "object", "properties": {}}


def test_flatten_call_result_text_content() -> None:
    class _Part:
        text = "hello"

    class _Result:
        content = [_Part(), _Part()]
        structuredContent = None

    out = _flatten_call_result(_Result())
    assert out == {"text": "hello\nhello"}


def test_flatten_call_result_empty_content_uses_structured() -> None:
    class _Result:
        content: list[object] = []
        structuredContent = {"ok": True, "rows": 3}

    assert _flatten_call_result(_Result()) == {"ok": True, "rows": 3}


def test_list_tools_against_demo_echo_server() -> None:
    from rath.flow.tool.mcp_adapter import MCPClient

    client = MCPClient([sys.executable, str(_DEMO_SERVER)])
    tools = client.list_tools()
    names = [t.name for t in tools]
    assert "echo" in names


def test_call_tool_round_trips_text() -> None:
    from rath.flow.tool.mcp_adapter import mcp_tools_from_server
    from rath.session import Session

    tools = mcp_tools_from_server([sys.executable, str(_DEMO_SERVER)])
    echo = next(t for t in tools if t.name == "echo")
    result = echo(Session.from_user_message("dummy"), {"text": "ping"})
    assert result == {"text": "ping"}


def test_mcp_tool_call_exposes_openai_style_schema() -> None:
    """``parameters`` must be a JSON-schema object suitable for OpenAI tools[]."""
    from rath.flow.tool.mcp_adapter import mcp_tools_from_server

    tools = mcp_tools_from_server([sys.executable, str(_DEMO_SERVER)])
    echo = next(t for t in tools if t.name == "echo")
    assert echo.parameters.get("type") == "object"
    assert "properties" in echo.parameters
    assert echo.description == "Echo the provided text back to the caller."
