"""Workflow wrapper that runs :func:`~rath.session.compress.run_session_compress`."""

from __future__ import annotations

from rath.flow.agent_param import AgentParam
from rath.flow.workflow import Workflow
from rath.llm.provider import Provider
from rath.session import ChunkAppendHook, Session, run_session_compress


class Compressor(Workflow):
    def __init__(
        self,
        compress_instruction: str,
        provider: Provider,
        *,
        chunk_print: ChunkAppendHook | None = None,
    ):
        super().__init__()
        self._chunk_print = chunk_print
        self.agent = AgentParam(
            agent_session=Session.from_agent_prompt(compress_instruction),
            provider=provider,
        )

    def forward(self, session: Session) -> Session:
        return run_session_compress(
            user_session=session,
            agent_session=self.agent.agent_session,
            agent_provider=self.agent.provider,
            chunk_print=self._chunk_print,
        )


__all__ = ["Compressor"]
