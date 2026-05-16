"""Tests for example/research_transformer (no live LLM calls)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

_OPENRATH_ROOT = Path(__file__).resolve().parents[2]
_EXAMPLE_ROOT = _OPENRATH_ROOT / "example"


def _prepend_example_path() -> None:
    root = str(_EXAMPLE_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _import_providers():
    _prepend_example_path()
    from research_transformer.providers import (
        providers_from_env,  # type: ignore[import-not-found]
    )

    return providers_from_env


def test_providers_from_env_requires_api_key() -> None:
    providers_from_env = _import_providers()
    with mock.patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="API_KEY"):
            providers_from_env()


def test_providers_from_env_with_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    providers_from_env = _import_providers()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    p = providers_from_env()
    assert p.packager.api_key == "sk-test"
    assert p.deai.api_key == "sk-test"


def test_prompt_constants_are_non_empty() -> None:
    _prepend_example_path()
    from research_transformer import prompts  # type: ignore[import-not-found]

    for name in (
        "PACKAGER_SYSTEM",
        "LITERATURE_SYSTEM",
        "REWRITE_SYSTEM",
        "QA_SYSTEM",
        "VERIFIER_SYSTEM",
        "JARGON_SYSTEM",
        "DEAI_SYSTEM",
        "COMPRESSOR_SYSTEM",
    ):
        assert len(getattr(prompts, name).strip()) > 40


def test_workflow_invokes_stations_in_pipeline_order() -> None:
    """layers=2 produces the documented call sequence: 11 loops + 2 compresses."""

    _prepend_example_path()
    from research_transformer.providers import (
        ResearchTransformerProviders,  # type: ignore[import-not-found]
    )
    from research_transformer.workflow import (
        ResearchTransformerWorkflow,  # type: ignore[import-not-found]
    )

    from rath.llm import Provider
    from rath.session.session import Session

    def _p(role: str) -> Provider:
        return Provider(api_key="k", model=role)

    prov = ResearchTransformerProviders(
        packager=_p("packager"),
        literature=_p("literature"),
        rewrite=_p("rewrite"),
        qa=_p("qa"),
        verifier=_p("verifier"),
        jargon=_p("jargon"),
        deai=_p("deai"),
        compressor=_p("compressor"),
    )
    user = Session.from_user_message("hello").to("local", spec=None)

    loop_models: list[str] = []
    compress_models: list[str] = []

    def _record_loop(*args, **kwargs):
        user_session = args[0] if args else kwargs["user_session"]
        provider = kwargs["agent_provider"]
        loop_models.append(provider.model or "")
        return user_session

    def _record_compress(*args, **kwargs):
        user_session = args[0] if args else kwargs["user_session"]
        provider = kwargs["agent_provider"]
        compress_models.append(provider.model or "")
        return user_session

    with (
        mock.patch(
            "research_transformer.workflow.run_session_loop",
            side_effect=_record_loop,
        ),
        mock.patch(
            "rath.flow.compressor.run_session_compress",
            side_effect=_record_compress,
        ),
    ):
        wf = ResearchTransformerWorkflow(
            prov,
            layers=2,
            thesis_excerpt="thesis body",
            ddl_note="soon",
            image_tools=None,
        )
        wf.forward(user)

    assert loop_models == [
        "packager",
        "literature",
        "rewrite",
        "literature",
        "rewrite",
        "qa",
        "verifier",
        "qa",
        "verifier",
        "jargon",
        "deai",
    ]
    assert compress_models == ["compressor", "compressor"]


def test_workflow_no_compress_skips_run_session_compress() -> None:
    _prepend_example_path()
    from research_transformer.providers import (
        ResearchTransformerProviders,  # type: ignore[import-not-found]
    )
    from research_transformer.workflow import (
        ResearchTransformerWorkflow,  # type: ignore[import-not-found]
    )

    from rath.llm import Provider
    from rath.session.session import Session

    stub = Provider(api_key="k", model="m")
    prov = ResearchTransformerProviders(
        packager=stub,
        literature=stub,
        rewrite=stub,
        qa=stub,
        verifier=stub,
        jargon=stub,
        deai=stub,
        compressor=stub,
    )
    user = Session.from_user_message("hello").to("local", spec=None)
    with (
        mock.patch(
            "research_transformer.workflow.run_session_loop",
            side_effect=lambda u, *_a, **_k: u,
        ),
        mock.patch(
            "rath.flow.compressor.run_session_compress",
        ) as m_comp,
    ):
        wf = ResearchTransformerWorkflow(
            prov,
            layers=1,
            thesis_excerpt="t",
            ddl_note="d",
            image_tools=None,
            enable_compress=False,
        )
        wf.forward(user)
    assert m_comp.call_count == 0


def test_main_fails_missing_thesis(tmp_path: Path) -> None:
    _prepend_example_path()
    from research_transformer.main import main  # type: ignore[import-not-found]

    rc = main(
        [
            "--research-question",
            "q",
            "--supervisor-notes",
            "s",
            "--thesis-path",
            str(tmp_path / "missing.txt"),
        ]
    )
    assert rc == 2


def test_main_rejects_non_positive_layers(tmp_path: Path) -> None:
    _prepend_example_path()
    from research_transformer.main import main  # type: ignore[import-not-found]

    thesis = tmp_path / "t.txt"
    thesis.write_text("x", encoding="utf-8")
    rc = main(
        [
            "--research-question",
            "q",
            "--supervisor-notes",
            "s",
            "--thesis-path",
            str(thesis),
            "--layers",
            "0",
        ]
    )
    assert rc == 2


def test_default_workspace_constant() -> None:
    _prepend_example_path()
    import importlib

    m = importlib.import_module("research_transformer.main")
    assert m.DEFAULT_WORKSPACE.name == ".workspace"
    assert m.DEFAULT_WORKSPACE.parent.name == "research_transformer"
