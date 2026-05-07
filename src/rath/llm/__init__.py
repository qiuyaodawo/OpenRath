"""OpenAI-compatible LLM access (synchronous chat completions)."""

from rath.llm.agent_llm_provider import AgentLLMProvider
from rath.llm.client import RathOpenAIChatClient
from rath.llm.openai_create_kwargs import to_create_kwargs
from rath.llm.openai_normalize import normalize_chat_completion
from rath.llm.settings import (
    RathLLMSettings,
    load_rath_llm_settings,
    rath_llm_default_dotenv_path,
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
    RathLLMTokenUsage,
    RathLLMToolCallFunction,
    RathLLMToolCallPart,
)

__all__ = [
    "AgentLLMProvider",
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
