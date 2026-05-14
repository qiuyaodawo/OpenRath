"""TradingAgents-style multi-phase Workflow."""

from __future__ import annotations

from agents import (
    ANALYST_SYSTEM,
    RESEARCHER_BEAR_SYSTEM,
    RESEARCHER_BULL_SYSTEM,
    RISK_PM_SYSTEM,
    TRADER_SYSTEM,
)
from tools import AlphaVantageGlobalQuoteTool

from rath.flow.agent_param import AgentParam, Provider
from rath.flow.workflow import Workflow
from rath.session import run_session_loop
from rath.session.loop import ChunkAppendHook
from rath.session.session import Session


class TradingAgentsWorkflow(Workflow):
    """Sequential analyst → bear → bull → trader → risk/PM."""

    def __init__(
        self, provider: Provider, *, chunk_print: ChunkAppendHook | None = None
    ) -> None:
        super().__init__()
        prov = provider
        self._chunk_print = chunk_print
        self.analyst = AgentParam(Session.from_agent_prompt(ANALYST_SYSTEM), prov)
        self.researcher_bear = AgentParam(
            Session.from_agent_prompt(RESEARCHER_BEAR_SYSTEM),
            prov,
        )
        self.researcher_bull = AgentParam(
            Session.from_agent_prompt(RESEARCHER_BULL_SYSTEM),
            prov,
        )
        self.trader = AgentParam(Session.from_agent_prompt(TRADER_SYSTEM), prov)
        self.risk_pm = AgentParam(Session.from_agent_prompt(RISK_PM_SYSTEM), prov)

    def forward(self, session: Session) -> Session:
        market_tools = [AlphaVantageGlobalQuoteTool()]
        cp = self._chunk_print
        s = run_session_loop(
            session,
            self.analyst.agent_session,
            agent_provider=self.analyst.provider,
            tools=market_tools,
            chunk_print=cp,
        )
        s = run_session_loop(
            s,
            self.researcher_bear.agent_session,
            agent_provider=self.researcher_bear.provider,
            tools=None,
            chunk_print=cp,
        )
        s = run_session_loop(
            s,
            self.researcher_bull.agent_session,
            agent_provider=self.researcher_bull.provider,
            tools=None,
            chunk_print=cp,
        )
        s = run_session_loop(
            s,
            self.trader.agent_session,
            agent_provider=self.trader.provider,
            tools=None,
            chunk_print=cp,
        )
        return run_session_loop(
            s,
            self.risk_pm.agent_session,
            agent_provider=self.risk_pm.provider,
            tools=None,
            chunk_print=cp,
        )
