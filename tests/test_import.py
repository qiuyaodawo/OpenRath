def test_import_rath() -> None:
    import rath

    assert rath is not None
    assert rath.backend is not None
    assert rath.flow is not None


def test_import_session_and_workflow_modules() -> None:
    """Session/workflow planes are optional imports (not loaded by ``import rath``)."""

    from rath.flow.workflow import SingleAgent, Workflow
    from rath.session import DefaultSessionLoopProvider, Session, run_session_loop

    assert Session.__name__ == "Session"
    assert Workflow.__name__ == "Workflow"
    assert SingleAgent.__name__ == "SingleAgent"
    assert run_session_loop.__name__ == "run_session_loop"
    assert DefaultSessionLoopProvider.__name__ == "DefaultSessionLoopProvider"
