"""OpenAI-compatible LLM access (synchronous chat completions)."""

from rath.llm._client import RathOpenAIChatClient
from rath.llm._openai_create_kwargs import to_create_kwargs
from rath.llm._openai_normalize import normalize_chat_completion
from rath.llm._settings import (
    RathLLMSettings,
    load_rath_llm_settings,
    rath_llm_default_dotenv_path,
)
from rath.llm._types_request import (
    RathLLMChatRequest,
    RathLLMFunctionTool,
    RathLLMMessage,
    RathLLMRole,
)
from rath.llm._types_response import (
    RathLLMAssistantMessage,
    RathLLMChatChoice,
    RathLLMChatResponse,
    RathLLMFinishReason,
    RathLLMTokenUsage,
    RathLLMToolCallFunction,
    RathLLMToolCallPart,
)

__all__ = [
    "RathOpenAIChatClient",
    "RathLLMSettings",
    "rath_llm_default_dotenv_path",
    "load_rath_llm_settings",
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
