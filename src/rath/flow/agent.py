from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Union

from rath.flow.agent_param import AgentParam
from rath.flow.memory_inject import DefaultRecallInjection, MemoryInjectionPolicy
from rath.flow.tool import FlowToolCall
from rath.flow.workflow import Workflow
from rath.llm import RathLLMStreamDelta
from rath.llm.provider import Provider
from rath.memory import current as _current_memory_backend
from rath.memory import get as _get_memory_backend
from rath.memory.abc import MemoryStore, MemoryStoreSpec
from rath.session import Session, run_session_loop


MemoryArg = Union[MemoryStore, MemoryStoreSpec, str, None]


def _resolve_memory(memory: MemoryArg) -> MemoryStore | None:
    """Resolve any of the three accepted ``memory=`` forms to an open store.

    Acquires one refcount on the returned store; the caller -- usually
    :class:`Agent` -- is responsible for releasing it via
    :meth:`MemoryStore.release` (or its own ``close()``).
    """

    if memory is None:
        return None
    if isinstance(memory, MemoryStore):
        return memory.acquire()
    if isinstance(memory, str):
        backend = _get_memory_backend(memory)
        return backend.open().acquire()
    if isinstance(memory, MemoryStoreSpec):
        backend = _current_memory_backend()
        return backend.open(memory).acquire()
    raise TypeError(
        f"memory must be a MemoryStore, MemoryStoreSpec, backend name, or None; got {type(memory).__name__}"
    )


class Agent(Workflow):
    def __init__(
        self,
        system_prompt: str,
        provider: Provider | None = None,
        tools: list[FlowToolCall] | None = None,
        *,
        model: str | None = None,
        on_event: Callable[[RathLLMStreamDelta], None] | None = None,
        memory: MemoryArg = None,
        memory_inject: MemoryInjectionPolicy | None = None,
        commit_on_forward: bool = False,
    ):
        """Build a single-agent workflow.

        ``provider`` may be a fully-formed :class:`~rath.llm.Provider` (the
        explicit form used when you want to control api_key, base_url,
        sampling, etc.) or omitted in favor of the shortcut ``model="..."``
        kwarg, which constructs a :class:`Provider` with just that model name.

        ``api_key`` and ``base_url`` left empty on the Provider fall back to
        the ``OPENAI_API_KEY`` / ``OPENAI_BASE_URL`` environment variables,
        then to ``llm.default_provider`` in ``~/.openrath/config.json``
        (see :mod:`rath.config`), inside
        :class:`~rath.llm.RathOpenAIChatClient`, so::

            flow.Agent("Use tools when helpful.", model="gpt-5.5")

        is the minimal form that works once the environment is configured.

        ``on_event`` enables streaming: each forward pass invokes the loop
        with the callback wired up. The resolved chat client must satisfy
        :class:`~rath.llm.StreamingChatClient`.
        """
        super().__init__()
        if provider is None and model is None:
            raise ValueError(
                'flow.Agent requires either provider=Provider(...) or model="..."',
            )
        if provider is None:
            provider = Provider(model=model)
        elif model is not None and provider.model is None:
            provider = replace(provider, model=model)
        self.tools = list(tools or [])
        self._on_event = on_event
        self._memory_inject: MemoryInjectionPolicy = memory_inject or DefaultRecallInjection()
        self._commit_on_forward = commit_on_forward
        resolved_memory = _resolve_memory(memory)
        self.memory = resolved_memory
        self.agent = AgentParam(
            agent_session=Session.from_agent_prompt(system_prompt),
            provider=provider,
            memory=resolved_memory,
        )

    def forward(self, session: Session) -> Session:
        return run_session_loop(
            user_session=session,
            agent_session=self.agent.agent_session,
            agent_provider=self.agent.provider,
            tools=self.tools,
            on_event=self._on_event,
        )

    def register_tool(self, tool: FlowToolCall) -> None:
        if any(t.name == tool.name for t in self.tools):
            return
        self.tools.append(tool)

    def unregister_tool(self, tool_name: str) -> None:
        self.tools = [t for t in self.tools if t.name != tool_name]
