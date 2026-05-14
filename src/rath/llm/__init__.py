"""OpenAI-compatible LLM access (synchronous chat completions)."""

from rath.llm._chat_client_proto import ChatClient
from rath.llm.provider import Provider
from rath.llm.client import RathOpenAIChatClient
from rath.llm.openai_create_kwargs import to_create_kwargs
from rath.llm.openai_normalize import normalize_chat_completion
from rath.llm.anthropic_normalize import (
    build_anthropic_kwargs,
    normalize_anthropic_response,
)
from rath.llm.chat_request import (
    RathLLMChatRequest,
    RathLLMFunctionTool,
    RathLLMMessage,
    RathLLMRole,
)
from rath.llm.chat_response import (
    RathLLMAssistantMessage,
    RathLLMChatChoice,
    RathLLMChatResponse,
    RathLLMFinishReason,
    RathLLMStreamDelta,
    RathLLMTokenUsage,
    RathLLMToolCallFunction,
    RathLLMToolCallPart,
    add_usage,
)


class BudgetExceededError(RuntimeError):
    """Raised by user code from ``Provider.on_budget_exceeded`` to abort a loop.

    The session loop itself does not raise this automatically when
    ``budget_total_tokens`` is exceeded - it only invokes the callback (or
    logs a warning if no callback is set). Raising this from the callback is
    the documented way to stop the loop on overrun.
    """


__all__ = [
    "ChatClient",
    "Provider",
    "RathOpenAIChatClient",
    "BudgetExceededError",
    "to_create_kwargs",
    "normalize_chat_completion",
    "build_anthropic_kwargs",
    "normalize_anthropic_response",
    "add_usage",
    "RathLLMChatRequest",
    "RathLLMMessage",
    "RathLLMFunctionTool",
    "RathLLMRole",
    "RathLLMChatResponse",
    "RathLLMChatChoice",
    "RathLLMAssistantMessage",
    "RathLLMFinishReason",
    "RathLLMStreamDelta",
    "RathLLMTokenUsage",
    "RathLLMToolCallPart",
    "RathLLMToolCallFunction",
]
