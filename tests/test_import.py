def test_import_rath() -> None:
    import rath

    assert rath is not None
    assert rath.backend is not None
    assert rath.flow is not None


def test_namespace_flow_submodules() -> None:
    """``rath.flow`` exposes the package; agent params and workflows live on submodules."""

    import rath
    from rath import flow

    assert rath.flow is flow

    from rath.flow.agent_param import AgentParam
    from rath.flow.workflow import Workflow, run_session_loop_from_agent
    from rath.llm import Provider

    assert flow.AgentParam is AgentParam
    assert AgentParam.__name__ == "AgentParam"
    assert Provider.__name__ == "Provider"
    assert Workflow.__name__ == "Workflow"
    assert run_session_loop_from_agent.__name__ == "run_session_loop_from_agent"


def test_provider_lives_in_llm_reexported_from_flow_agent_param() -> None:
    from rath.flow.agent_param import Provider as FromFlow
    from rath.llm import Provider as FromLlm

    assert FromFlow is FromLlm


def test_import_session_and_flow_modules() -> None:
    """Session and flow types import from their submodules."""

    from rath.flow.agent_param import AgentParam
    from rath.flow.workflow import Workflow
    from rath.llm import Provider
    from rath.session import (
        DefaultSessionLoopExecutor,
        Session,
        SessionLoopExecutor,
        run_session_loop,
    )

    assert AgentParam.__name__ == "AgentParam"
    assert Provider.__name__ == "Provider"
    assert Workflow.__name__ == "Workflow"
    assert Session.__name__ == "Session"
    assert run_session_loop.__name__ == "run_session_loop"
    assert DefaultSessionLoopExecutor.__name__ == "DefaultSessionLoopExecutor"
    assert SessionLoopExecutor.__name__ == "SessionLoopExecutor"
