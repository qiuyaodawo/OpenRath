import rath
import rath.flow as flow
from rath.session import Session, run_session_loop


class SingAgentWorkflow(flow.Workflow):
    def __init__(self, system_prompt: str, model: str):
        super().__init__()
        self.agent = flow.Agent(
            agent_session=Session.from_agent_prompt(system_prompt),
            provider=flow.Provider(model=model),
        )

    def forward(self, session: Session) -> Session:
        return run_session_loop(
            user_session=session,
            agent_session=self.agent.agent_session,
            agent_provider=self.agent.provider,
        )


if __name__ == "__main__":
    agent_wf = SingAgentWorkflow(
        system_prompt="You are a helpful assistant.",
        model="glm-5.1",
    )
    print(agent_wf)

    user_session = Session.from_user_message(
        "Please summarize this repository in one short paragraph."
    ).to("local", spec="./")
    out_session = agent_wf.forward(user_session)
    print(out_session)
