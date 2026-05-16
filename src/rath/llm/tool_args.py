"""Shared JSON parser for LLM ``tool_calls[*].function.arguments`` strings.

Both vendors stream tool-call arguments as a single JSON string. Normalizers in
:mod:`rath.llm.openai.normalize`, :mod:`rath.llm.anthropic.create_kwargs`, and
the streaming accumulator in :mod:`rath.session.loop` all need the same
"parse to a ``dict``, or report a parse error" semantics.
"""

from __future__ import annotations

import json
from typing import Any

__all__ = ["parse_tool_arguments"]


def parse_tool_arguments(arg_str: str | None) -> tuple[dict[str, Any] | None, bool]:
    """Parse an ``arguments`` JSON string into ``(parsed_dict_or_none, had_error)``.

    Returns ``(None, False)`` for an empty / missing input (the model did not
    emit any arguments). Returns ``(None, True)`` when the string is non-empty
    but either fails JSON parsing or decodes to something other than an object
    — callers preserve the original ``arg_str`` to surface to the user.
    """
    if not arg_str:
        return None, False
    try:
        val: Any = json.loads(arg_str)
    except (ValueError, TypeError):
        return None, True
    if isinstance(val, dict):
        return val, False
    return None, True
