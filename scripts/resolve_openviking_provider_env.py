"""Resolve OpenViking embedding/VLM credentials for launch scripts.

Priority:
1. ``OPEN_VIKING_EMBEDDING_API_KEY`` / ``OPEN_VIKING_VLM_API_KEY`` (and optional bases)
2. ``~/.openrath/config.json`` via :class:`EmbeddingProvider` / :class:`VLMProvider`
3. ``OPENAI_API_KEY`` / ``OPENAI_BASE_URL`` as a last resort for both roles

Prints ``KEY=VALUE`` lines suitable for ``eval "$(uv run python ...)"`` in bash.
Exits with status 1 and a stderr message when no key is available.
"""

from __future__ import annotations

import os
import sys


def _resolve() -> dict[str, str]:
    emb_key = os.environ.get("OPEN_VIKING_EMBEDDING_API_KEY", "").strip()
    vlm_key = os.environ.get("OPEN_VIKING_VLM_API_KEY", "").strip()
    emb_base = os.environ.get("OPEN_VIKING_EMBEDDING_API_BASE", "").strip()
    vlm_base = os.environ.get("OPEN_VIKING_VLM_API_BASE", "").strip()
    emb_model = os.environ.get("OPEN_VIKING_EMBEDDING_MODEL", "embedding-3").strip()
    emb_dim = os.environ.get("OPEN_VIKING_EMBEDDING_DIMENSION", "2048").strip()
    vlm_model = os.environ.get("OPEN_VIKING_VLM_MODEL", "glm-4.6v").strip()

    if not emb_key or not vlm_key:
        try:
            from rath.llm.embedding import EmbeddingProvider

            ep = EmbeddingProvider.from_config()
            if not emb_key and ep.api_key:
                emb_key = ep.api_key.strip()
            if not emb_base and ep.base_url:
                emb_base = ep.base_url.strip()
            if ep.model:
                emb_model = ep.model
        except Exception:
            pass
        if not vlm_key:
            try:
                from rath.llm.vlm import VLMProvider

                vp = VLMProvider.from_config()
                if vp.api_key:
                    vlm_key = vp.api_key.strip()
                if not vlm_base and vp.base_url:
                    vlm_base = vp.base_url.strip()
                if vp.model:
                    vlm_model = vp.model
            except Exception:
                pass

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    openai_base = os.environ.get("OPENAI_BASE_URL", "").strip()
    if not emb_key and openai_key:
        emb_key = openai_key
    if not vlm_key and openai_key:
        vlm_key = openai_key
    if not emb_base and openai_base:
        emb_base = openai_base
    if not vlm_base and openai_base:
        vlm_base = openai_base

    if not emb_base:
        emb_base = "https://api.openai.com/v1"
    if not vlm_base:
        vlm_base = emb_base

    if not emb_key or not vlm_key:
        print(
            "error: OpenViking needs embedding and VLM API keys.\n"
            "  export OPEN_VIKING_EMBEDDING_API_KEY and OPEN_VIKING_VLM_API_KEY, or\n"
            "  configure llm.embedding_provider / llm.vlm_provider in "
            "~/.openrath/config.json, or\n"
            "  export OPENAI_API_KEY (and optionally OPENAI_BASE_URL).",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return {
        "OPEN_VIKING_EMBEDDING_API_KEY": emb_key,
        "OPEN_VIKING_EMBEDDING_API_BASE": emb_base,
        "OPEN_VIKING_EMBEDDING_MODEL": emb_model,
        "OPEN_VIKING_EMBEDDING_DIMENSION": emb_dim,
        "OPEN_VIKING_VLM_API_KEY": vlm_key,
        "OPEN_VIKING_VLM_API_BASE": vlm_base,
        "OPEN_VIKING_VLM_MODEL": vlm_model,
    }


def main() -> None:
    for key, value in _resolve().items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
