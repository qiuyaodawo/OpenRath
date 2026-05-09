from rath.session import Session


def main() -> None:
    # Session Create
    agent = Session.from_agent_prompt("You are a helpful assistant.")
    user = Session.from_user_message("Hello, how are you?")
    print(agent)
    print(user)

    # Session Merge
    merged = agent + user
    print(merged)

    # Session Fork
    forked = merged.fork()
    print(forked)

    # Session Detach
    detached = forked.detach()
    print(detached)


if __name__ == "__main__":
    main()
