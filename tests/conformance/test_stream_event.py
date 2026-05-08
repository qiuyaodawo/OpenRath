"""Stream and :class:`Event` semantics on each registered backend."""

from __future__ import annotations

from rath.backend import (
    Backend,
    CommandResult,
    FileContent,
    BackendToolCommandRun,
    BackendToolFilesRead,
    BackendToolFilesWrite,
)


def test_fifo_within_one_stream(backend: Backend, python_cmd: list[str]) -> None:
    """A dependency chain expressed via stream submission must be honoured."""
    with backend.open() as sb:
        with sb.stream() as s:
            s.submit(BackendToolFilesWrite(path="step.txt", data="a"))
            s.submit(
                BackendToolCommandRun(
                    cmd=[
                        *python_cmd,
                        "-c",
                        (
                            "import pathlib;"
                            " pathlib.Path('step.txt').write_text("
                            " pathlib.Path('step.txt').read_text() + 'b')"
                        ),
                    ]
                )
            )
            f3 = s.submit(BackendToolFilesRead(path="step.txt"))
            res = f3.result()
    assert isinstance(res, FileContent)
    assert res.data == "ab"


def test_two_streams_progress_concurrently(
    backend: Backend, python_cmd: list[str]
) -> None:
    """Two streams over the same sandbox should overlap their work."""
    with backend.open() as sb:
        with sb.stream() as s1, sb.stream() as s2:
            f1 = s1.submit(
                BackendToolCommandRun(
                    cmd=[
                        *python_cmd,
                        "-c",
                        "import time; time.sleep(0.2); print('one')",
                    ]
                )
            )
            f2 = s2.submit(
                BackendToolCommandRun(
                    cmd=[
                        *python_cmd,
                        "-c",
                        "import time; time.sleep(0.2); print('two')",
                    ]
                )
            )
            r1 = f1.result()
            r2 = f2.result()

    assert isinstance(r1, CommandResult)
    assert isinstance(r2, CommandResult)
    assert b"one" in r1.stdout
    assert b"two" in r2.stdout


def test_event_orders_across_streams(backend: Backend) -> None:
    """An event recorded on s1 must gate s2's subsequent submissions."""
    with backend.open() as sb:
        with sb.stream() as s1, sb.stream() as s2:
            s1.submit(BackendToolFilesWrite(path="ordered.txt", data="hello"))
            evt = s1.record_event()
            s2.wait_event(evt)
            f = s2.submit(BackendToolFilesRead(path="ordered.txt"))
            res = f.result()
    assert isinstance(res, FileContent)
    assert res.data == "hello"


def test_synchronize_drains_stream(backend: Backend) -> None:
    with backend.open() as sb:
        with sb.stream() as s:
            for i in range(3):
                s.submit(BackendToolFilesWrite(path=f"f{i}.txt", data=str(i)))
            s.synchronize()
            for i in range(3):
                f = s.submit(BackendToolFilesRead(path=f"f{i}.txt"))
                res = f.result()
                assert isinstance(res, FileContent)
                assert res.data == str(i)
