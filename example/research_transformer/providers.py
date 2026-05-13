"""Load per-role :class:`~rath.llm.provider.Provider` from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from rath.llm import Provider


@dataclass(frozen=True, slots=True)
class ResearchTransformerProviders:
    """One OpenAI-compatible client configuration per pipeline station."""

    packager: Provider
    literature: Provider
    rewrite: Provider
    qa: Provider
    verifier: Provider
    jargon: Provider
    deai: Provider
    compressor: Provider


def _strip(key: str) -> str:
    return os.environ.get(key, "").strip()


def _resolve_api_key() -> str:
    """RESEARCH_TRANSFORMER_API_KEY then OPENAI_API_KEY."""

    key = _strip("RESEARCH_TRANSFORMER_API_KEY") or _strip("OPENAI_API_KEY")
    if not key:
        raise ValueError(
            "API_KEY is required: set OPENAI_API_KEY or RESEARCH_TRANSFORMER_API_KEY"
        )
    return key


def _resolve_base_url() -> str | None:
    url = _strip("RESEARCH_TRANSFORMER_BASE_URL") or _strip("OPENAI_BASE_URL")
    return url or None


def _default_model() -> str | None:
    m = _strip("OPENAI_DEFAULT_MODEL")
    return m or None


def _model_for(env_key: str) -> str | None:
    m = _strip(env_key)
    return m if m else _default_model()


def _one_provider(*, model_env: str) -> Provider:
    return Provider(
        api_key=_resolve_api_key(),
        base_url=_resolve_base_url(),
        model=_model_for(model_env),
    )


def providers_from_env() -> ResearchTransformerProviders:
    """Build providers from ``RESEARCH_TRANSFORMER_*`` and ``OPENAI_*`` env."""

    return ResearchTransformerProviders(
        packager=_one_provider(model_env="RESEARCH_TRANSFORMER_MODEL_PACKAGER"),
        literature=_one_provider(model_env="RESEARCH_TRANSFORMER_MODEL_LITERATURE"),
        rewrite=_one_provider(model_env="RESEARCH_TRANSFORMER_MODEL_REWRITE"),
        qa=_one_provider(model_env="RESEARCH_TRANSFORMER_MODEL_QA"),
        verifier=_one_provider(model_env="RESEARCH_TRANSFORMER_MODEL_VERIFIER"),
        jargon=_one_provider(model_env="RESEARCH_TRANSFORMER_MODEL_JARGON"),
        deai=_one_provider(model_env="RESEARCH_TRANSFORMER_MODEL_DEAI"),
        compressor=_one_provider(model_env="RESEARCH_TRANSFORMER_MODEL_COMPRESSOR"),
    )
