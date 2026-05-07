def test_import_rath() -> None:
    import rath

    assert rath is not None
    assert rath.backend is not None
    assert rath.flow is not None


def test_namespace_flow_submodules() -> None:
    """``rath.flow`` exposes the package; agents and workflows live on submodules."""

    import rath
    from rath import flow

    assert rath.flow is flow

    from rath.flow.agent import Agent, AgentLLMProvider
    from rath.flow.workflow import Workflow

    assert Agent.__name__ == "Agent"
    assert AgentLLMProvider.__name__ == "AgentLLMProvider"
    assert Workflow.__name__ == "Workflow"


def test_import_session_and_flow_modules() -> None:
    """Session and flow types import from their submodules."""

    from rath.flow.agent import Agent, AgentLLMProvider
    from rath.flow.workflow import Workflow
    from rath.session import (
        DefaultSessionLoopExecutor,
        Session,
        SessionLoopExecutor,
        run_session_loop,
    )

    assert Agent.__name__ == "Agent"
    assert AgentLLMProvider.__name__ == "AgentLLMProvider"
    assert Workflow.__name__ == "Workflow"
    assert Session.__name__ == "Session"
    assert run_session_loop.__name__ == "run_session_loop"
    assert DefaultSessionLoopExecutor.__name__ == "DefaultSessionLoopExecutor"
    assert SessionLoopExecutor.__name__ == "SessionLoopExecutor"
