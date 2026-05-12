"""Multi-branch workflows for the Research Transformer example."""

from __future__ import annotations

from rath.flow.agent_param import AgentParam
from rath.flow.compressor import Compressor
from rath.flow.tool import FlowToolCall
from rath.flow.workflow import Workflow
from rath.session import run_session_loop
from rath.session.chunk import user_text_chunk
from rath.session.loop import ChunkAppendHook
from rath.session.session import Session

from research_transformer.prompts import (
    COMPRESSOR_SYSTEM,
    DEAI_SYSTEM,
    JARGON_SYSTEM,
    LITERATURE_SYSTEM,
    PACKAGER_SYSTEM,
    QA_SYSTEM,
    REWRITE_SYSTEM,
    VERIFIER_SYSTEM,
)
from research_transformer.providers import ResearchTransformerProviders


class LiteratureBranchWorkflow(Workflow):
    """Packager plus N×(literature → rewrite)."""

    def __init__(
        self,
        prov: ResearchTransformerProviders,
        layers: int,
        *,
        chunk_print: ChunkAppendHook | None = None,
    ) -> None:
        super().__init__()
        if layers < 1:
            raise ValueError("layers must be >= 1")
        self.layers = layers
        self._chunk_print = chunk_print
        self.packager = AgentParam(Session.from_agent_prompt(PACKAGER_SYSTEM), prov.packager)
        self.literature = AgentParam(
            Session.from_agent_prompt(LITERATURE_SYSTEM),
            prov.literature,
        )
        self.rewrite = AgentParam(Session.from_agent_prompt(REWRITE_SYSTEM), prov.rewrite)

    def forward(self, session: Session) -> Session:
        cp = self._chunk_print
        s = run_session_loop(
            session,
            self.packager.agent_session,
            agent_provider=self.packager.provider,
            chunk_print=cp,
        )
        for _ in range(self.layers):
            s = run_session_loop(
                s,
                self.literature.agent_session,
                agent_provider=self.literature.provider,
                chunk_print=cp,
            )
            s = run_session_loop(
                s,
                self.rewrite.agent_session,
                agent_provider=self.rewrite.provider,
                chunk_print=cp,
            )
        return s


class ReproductionBranchWorkflow(Workflow):
    """Append thesis context, then N×(QA → verifier with optional image tools)."""

    def __init__(
        self,
        prov: ResearchTransformerProviders,
        layers: int,
        *,
        thesis_excerpt: str,
        ddl_note: str,
        image_tools: list[FlowToolCall] | None,
        chunk_print: ChunkAppendHook | None = None,
    ) -> None:
        super().__init__()
        if layers < 1:
            raise ValueError("layers must be >= 1")
        self.layers = layers
        self._thesis_excerpt = thesis_excerpt
        self._ddl_note = ddl_note
        self._image_tools = image_tools
        self._chunk_print = chunk_print
        self.qa = AgentParam(Session.from_agent_prompt(QA_SYSTEM), prov.qa)
        self.verifier = AgentParam(Session.from_agent_prompt(VERIFIER_SYSTEM), prov.verifier)

    def forward(self, session: Session) -> Session:
        preamble = (
            "## Branch B: reproduction track (thesis / DDL)\n\n"
            "### Senior thesis excerpt\n"
            f"{self._thesis_excerpt.strip()}\n\n"
            "### Deadline / pressure\n"
            f"{self._ddl_note.strip()}\n"
        )
        session.chunk_table = session.chunk_table.extend(user_text_chunk(preamble))
        if self._chunk_print is not None:
            rows = session.chunk_table.rows
            self._chunk_print(rows[-1], len(rows) - 1, session)
        s = session
        cp = self._chunk_print
        for _ in range(self.layers):
            s = run_session_loop(
                s,
                self.qa.agent_session,
                agent_provider=self.qa.provider,
                chunk_print=cp,
            )
            s = run_session_loop(
                s,
                self.verifier.agent_session,
                agent_provider=self.verifier.provider,
                tools=self._image_tools,
                chunk_print=cp,
            )
        return s


class OutputHeadWorkflow(Workflow):
    """Academic register → de-AI polish."""

    def __init__(
        self,
        prov: ResearchTransformerProviders,
        *,
        chunk_print: ChunkAppendHook | None = None,
    ) -> None:
        super().__init__()
        self._chunk_print = chunk_print
        self.jargon = AgentParam(Session.from_agent_prompt(JARGON_SYSTEM), prov.jargon)
        self.deai = AgentParam(Session.from_agent_prompt(DEAI_SYSTEM), prov.deai)

    def forward(self, session: Session) -> Session:
        cp = self._chunk_print
        s = run_session_loop(
            session,
            self.jargon.agent_session,
            agent_provider=self.jargon.provider,
            chunk_print=cp,
        )
        return run_session_loop(
            s,
            self.deai.agent_session,
            agent_provider=self.deai.provider,
            chunk_print=cp,
        )


class ResearchTransformerWorkflow(Workflow):
    """Full stack: literature branch → compress → reproduction branch → compress → head."""

    def __init__(
        self,
        providers: ResearchTransformerProviders,
        *,
        layers: int,
        thesis_excerpt: str,
        ddl_note: str,
        image_tools: list[FlowToolCall] | None,
        enable_compress: bool = True,
        chunk_print: ChunkAppendHook | None = None,
    ) -> None:
        super().__init__()
        cp = chunk_print
        self._literature = LiteratureBranchWorkflow(
            providers, layers, chunk_print=cp
        )
        self._repro = ReproductionBranchWorkflow(
            providers,
            layers,
            thesis_excerpt=thesis_excerpt,
            ddl_note=ddl_note,
            image_tools=image_tools,
            chunk_print=cp,
        )
        self._head = OutputHeadWorkflow(providers, chunk_print=cp)
        self._enable_compress = enable_compress
        self._compressor = Compressor(
            COMPRESSOR_SYSTEM,
            providers.compressor,
            chunk_print=cp,
        )

    def forward(self, session: Session) -> Session:
        s = self._literature.forward(session)
        if self._enable_compress:
            s = self._compressor.forward(s)
        s = self._repro.forward(s)
        if self._enable_compress:
            s = self._compressor.forward(s)
        return self._head.forward(s)
