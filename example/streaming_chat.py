"""Print assistant tokens as they stream in.

Requires ``OPENAI_API_KEY`` to be set in the environment, **or** an
``llm.default_provider`` with an api_key in ``~/.openrath/config.json``.

Run::

    python example/streaming_chat.py
"""

from __future__ import annotations

import os
import sys

from rath.config.store import ConfigStore
from rath.flow.agent_param import AgentParam, Provider
from rath.llm import RathLLMStreamDelta, RathOpenAIChatClient
from rath.session import Session
from rath.session.loop_stream import run_session_loop_stream


def _has_openai_credentials() -> bool:
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return True
    try:
        store = ConfigStore.load()
    except (FileNotFoundError, RuntimeError):
        return False
    default = store.config.llm.default_provider
    if default is None:
        return False
    entry = store.config.llm.providers.get(default)
    return bool(entry and entry.api_key)


def main() -> None:
    if not _has_openai_credentials():
        print(
            "No OpenAI credentials found: export OPENAI_API_KEY or "
            "configure llm.default_provider in ~/.openrath/config.json.",
            file=sys.stderr,
        )
        sys.exit(1)

    provider = Provider(model="glm-5.1")
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
