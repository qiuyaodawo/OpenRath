"""Print assistant tokens as they stream in.

Requires ``OPENAI_API_KEY`` to be set (or in a project ``.env``).

Run::

    python example/streaming_chat.py
"""

from __future__ import annotations

import os
import sys

from rath.flow.agent_param import AgentParam, Provider
from rath.llm import RathLLMStreamDelta, RathOpenAIChatClient
from rath.session import Session
from rath.session.loop_stream import run_session_loop_stream


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "OPENAI_API_KEY is not set; export it or add to .env",
            file=sys.stderr,
        )
        sys.exit(1)

    provider = Provider(model="gpt-5.5")
    client = RathOpenAIChatClient(provider)
    agent = AgentParam(
        Session.from_agent_prompt("You are a concise assistant."),
        provider,
    )

    def on_event(delta: RathLLMStreamDelta) -> None:
        if delta.content_delta:
            sys.stdout.write(delta.content_delta)
            sys.stdout.flush()
        if delta.finish_reason is not None:
            sys.stdout.write("\n")

    user = Session.from_user_message(
        "Count from 1 to 5 with a one-line note about each number."
    ).to("local")

    out = run_session_loop_stream(
        user,
        agent.agent_session,
        agent_provider=agent.provider,
        client=client,
        on_event=on_event,
    )

    if out.cumulative_usage is not None:
        print(
            f"--- usage total={out.cumulative_usage.total_tokens} "
            f"(prompt={out.cumulative_usage.prompt_tokens}, "
            f"completion={out.cumulative_usage.completion_tokens})"
        )


if __name__ == "__main__":
    main()
