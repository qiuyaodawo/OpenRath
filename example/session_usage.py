from dataclasses import replace

from _on_event import example_on_event
from _openai_provider import provider_from_env

from rath.session import Session, run_session_compress, run_session_loop


def session_usage() -> None:
    Session.from_agent_prompt("You are a helpful assistant.")
    user_session = Session.from_user_message("Hello, how are you?")
    forked_user = user_session.fork()
    _ = forked_user.detach()


if __name__ == "__main__":
    agent_session = Session.from_agent_prompt("You are a helpful assistant.")
    user_session = Session.from_user_message(
        "Please use tool to summarize this workspace. And return the summary."
    )
    user_session = user_session.to("local", spec="./")
    provider = replace(provider_from_env(), model="glm-5.1")
    out_session = run_session_loop(
        user_session=user_session,
        agent_session=agent_session,
        agent_provider=provider,
        on_event=example_on_event(),
    )

    out_session = run_session_compress(
        user_session=out_session,
        agent_session=agent_session,
        agent_provider=provider,
        on_event=example_on_event(),
    )
