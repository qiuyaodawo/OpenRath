from __future__ import annotations

from rath.flow.workflow import Workflow
from rath.flow.agent_param import AgentParam
from rath.flow.tool import FlowToolCall
from rath.session import Session, run_session_loop
from rath.llm.provider import Provider


class Agent(Workflow):
    def __init__(
        self,
        system_prompt: str,
        model: str,
        tools: list[FlowToolCall] | None = None,
    ):
        super().__init__()
        self.tools = list(tools or [])
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

    def register_tool(self, tool: FlowToolCall) -> None:
        if any(t.name == tool.name for t in self.tools):
            return
        self.tools.append(tool)

    def unregister_tool(self, tool_name: str) -> None:
        self.tools = [t for t in self.tools if t.name != tool_name]
