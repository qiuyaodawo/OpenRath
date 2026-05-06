"""Rath ↔ OpenAI-wire dict fidelity for tricky message fields."""

from __future__ import annotations

from rath.llm import RathLLMChatRequest, RathLLMMessage, to_create_kwargs


def test_to_create_kwargs_includes_assistant_tool_calls() -> None:
    wire_tc = (
        {
            "id": "tc1",
            "type": "function",
            "function": {"name": "run_shell_command", "arguments": '{"cmd":"noop"}'},
        },
    )
    msg = RathLLMMessage(
        role="assistant",
        content=None,
        tool_calls=tuple(dict(x) for x in wire_tc),
    )
    req = RathLLMChatRequest(messages=(msg,), model="gpt-test-wire")
    kwargs = to_create_kwargs(req, default_model=None)
    out_msgs = kwargs["messages"]
    assert len(out_msgs) == 1
    assert out_msgs[0]["role"] == "assistant"
    assert "tool_calls" in out_msgs[0]
    assert out_msgs[0]["tool_calls"][0]["function"]["name"] == "run_shell_command"
