from rath.flow.workflow import Workflow
from rath.flow.agent_param import AgentParam
from rath.session import Session, run_session_compress
from rath.llm.provider import Provider


class SessionCompressor(Workflow):
    def __init__(self, compress_instruction: str, model: str):
        super().__init__()
        self.agent = AgentParam(
            agent_session=Session.from_agent_prompt(compress_instruction),
            provider=Provider(model=model),
        )

    def forward(self, session: Session) -> Session:
        return run_session_compress(
            user_session=session,
            agent_session=self.agent.agent_session,
            agent_provider=self.agent.provider,
        )