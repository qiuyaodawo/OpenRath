from rath.flow.workflow import Workflow
from rath.flow.agent_param import AgentParam
from rath.session import Session, run_session_loop
from rath.llm.provider import Provider


class Agent(Workflow):
    def __init__(self, system_prompt: str, model: str, tools: list[str] = None):
        super().__init__()
        self.tools = tools or []
        self.agent = AgentParam(
            agent_session=Session.from_agent_prompt(system_prompt),
            provider=Provider(model=model),
        )

    def forward(self, session: Session) -> Session:
        return run_session_loop(
            user_session=session,
            agent_session=self.agent.agent_session,
            agent_provider=self.agent.provider,
            tools=self.tools,
        )

    def register_tool(self, tool_name: str):
        if tool_name not in self.tools:
            self.tools.append(tool_name)

    def unregister_tool(self, tool_name: str):
        if tool_name in self.tools:
            self.tools.remove(tool_name)