"""OpenAI-compatible LLM access (synchronous chat completions)."""

from rath.llm.provider import Provider
from rath.llm.client import RathOpenAIChatClient
from rath.llm.openai_create_kwargs import to_create_kwargs
from rath.llm.openai_normalize import normalize_chat_completion
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
    RathLLMTokenUsage,
    RathLLMToolCallFunction,
    RathLLMToolCallPart,
)

__all__ = [
    "Provider",
    "RathOpenAIChatClient",
    "to_create_kwargs",
    "normalize_chat_completion",
    "RathLLMChatRequest",
    "RathLLMMessage",
    "RathLLMFunctionTool",
    "RathLLMRole",
    "RathLLMChatResponse",
    "RathLLMChatChoice",
    "RathLLMAssistantMessage",
    "RathLLMFinishReason",
    "RathLLMTokenUsage",
    "RathLLMToolCallPart",
    "RathLLMToolCallFunction",
]
