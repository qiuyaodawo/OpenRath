"""Nested Workflow classes: outer project → feature squad → backend pair → QA."""

from __future__ import annotations

from rath.flow.agent_param import AgentParam, Provider
from rath.flow.workflow import Workflow
from rath.session import run_session_loop
from rath.session.session import Session

from agents import (
    ARCHITECT_SYSTEM,
    BACKEND_AUTH_SYSTEM,
    BACKEND_DATA_SYSTEM,
    FRONTEND_SYSTEM,
    LEAD_ENGINEER_SYSTEM,
    QA_SYSTEM,
)


class BackendPairWorkflow(Workflow):
    """L3: sequential auth then data backend (T2 → T3 after architect context)."""

    def __init__(self, prov: Provider) -> None:
        super().__init__()
        self.backend_auth = AgentParam(
            Session.from_agent_prompt(BACKEND_AUTH_SYSTEM),
            prov,
        )
        self.backend_data = AgentParam(
            Session.from_agent_prompt(BACKEND_DATA_SYSTEM),
            prov,
        )

    def forward(self, session: Session) -> Session:
        s = run_session_loop(
            session,
            self.backend_auth.agent_session,
            agent_provider=self.backend_auth.provider,
            tools=None,
        )
        return run_session_loop(
            s,
            self.backend_data.agent_session,
            agent_provider=self.backend_data.provider,
            tools=None,
        )


class FeatureSquadWorkflow(Workflow):
    """L2: architect → nested backend pair → frontend."""

    def __init__(self, prov: Provider) -> None:
        super().__init__()
        self.architect = AgentParam(Session.from_agent_prompt(ARCHITECT_SYSTEM), prov)
        self._backends = BackendPairWorkflow(prov)
        self.frontend = AgentParam(Session.from_agent_prompt(FRONTEND_SYSTEM), prov)

    def forward(self, session: Session) -> Session:
        s = run_session_loop(
            session,
            self.architect.agent_session,
            agent_provider=self.architect.provider,
            tools=None,
        )
        s = self._backends.forward(s)
        return run_session_loop(
            s,
            self.frontend.agent_session,
            agent_provider=self.frontend.provider,
            tools=None,
        )


class QualityAssuranceWorkflow(Workflow):
    """Post-implementation QA pass (T5 style)."""

    def __init__(self, prov: Provider) -> None:
        super().__init__()
        self.tester = AgentParam(Session.from_agent_prompt(QA_SYSTEM), prov)

    def forward(self, session: Session) -> Session:
        return run_session_loop(
            session,
            self.tester.agent_session,
            agent_provider=self.tester.provider,
            tools=None,
        )


class EngineeringProjectWorkflow(Workflow):
    """L1: lead plan, nested FeatureSquadWorkflow, then QualityAssuranceWorkflow."""

    def __init__(self, model: str) -> None:
        super().__init__()
        prov = Provider(model=model)
        self.lead = AgentParam(Session.from_agent_prompt(LEAD_ENGINEER_SYSTEM), prov)
        self._squad = FeatureSquadWorkflow(prov)
        self._qa = QualityAssuranceWorkflow(prov)

    def forward(self, session: Session) -> Session:
        s = run_session_loop(
            session,
            self.lead.agent_session,
            agent_provider=self.lead.provider,
            tools=None,
        )
        s = self._squad.forward(s)
        return self._qa.forward(s)
