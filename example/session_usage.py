from rath import flow
from rath.session import Session, run_session_loop, run_session_compress


def session_usage() -> None:
    agent_session = Session.from_agent_prompt("You are a helpful assistant.")
    user_session = Session.from_user_message("Hello, how are you?")
    forked_user = user_session.fork()
    detached_user = forked_user.detach()


if __name__ == "__main__":
    agent_session = Session.from_agent_prompt("You are a helpful assistant.")
    user_session = Session.from_user_message(
        "Please use tool to summarize this workspace. And return the summary."
    )
    user_session = user_session.to("local", spec="./")
    provider = flow.Provider(model="glm-5.1")
    out_session = run_session_loop(
        user_session=user_session,
        agent_session=agent_session,
        agent_provider=provider,
    )
    print(out_session)

    out_session = run_session_compress(
        user_session=out_session,
        agent_session=agent_session,
        agent_provider=provider,
    )
    print(out_session)
