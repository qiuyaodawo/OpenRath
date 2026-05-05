def test_import_rath() -> None:
    import rath

    assert rath is not None
    assert rath.backend is not None
    assert rath.flow is not None
