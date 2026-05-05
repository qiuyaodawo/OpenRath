"""LocalBackend: subprocess + filesystem on the host machine.

Acts as the fallback backend, analogous to PyTorch's CPU device. It is always
available and has the lowest cold-start cost. Paths in tool calls are resolved
relative to the sandbox's working directory when given as relative paths;
absolute paths are used as-is.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import sys
import tempfile
import time
import uuid
from collections.abc import Iterator
from typing import ClassVar

import anyio

from rath.backend._abc import Backend, BackendSandbox, BackendSandboxSpec
from rath.backend._capabilities import Capabilities, IsolationLevel
from rath.backend._errors import BackendSandboxClosed, UnsupportedFlowToolCall
from rath.flow.tool import (
    FlowToolCall,
    FlowToolCodeRun,
    FlowToolCommandRun,
    FlowToolFilesExists,
    FlowToolFilesList,
    FlowToolFilesRead,
    FlowToolFilesWrite,
)
from rath.backend._registry import register
from rath.backend._results import (
    CodeResult,
    CommandResult,
    FileContent,
    FileEntries,
    FileEntry,
    FileWriteResult,
    ToolResult,
)


@contextlib.contextmanager
def _maybe_timeout(seconds: float | None) -> Iterator[None]:
    """Apply ``anyio.fail_after`` only when ``seconds`` is set."""
    if seconds is None:
        yield
    else:
        with anyio.fail_after(seconds):
            yield


@register("local")
class LocalBackend(Backend):
    """Run tool calls as host-side subprocesses with a per-sandbox working dir."""

    name: ClassVar[str] = "local"

    _CAPABILITIES: ClassVar[Capabilities] = Capabilities(
        isolation=IsolationLevel.PROCESS,
        supports_command=True,
        supports_filesystem=True,
        supports_code_interpreter=True,
        cold_start_ms_p50=10,
        max_sandboxes=None,
    )

    _SUPPORTED_CALLS: ClassVar[frozenset[type[FlowToolCall]]] = frozenset(
        {
            FlowToolCommandRun,
            FlowToolFilesRead,
            FlowToolFilesWrite,
            FlowToolFilesList,
            FlowToolFilesExists,
            FlowToolCodeRun,
        }
    )

    def __init__(self) -> None:
        self._open_handles: set[str] = set()

    @classmethod
    def is_available(cls) -> bool:
        return True

    @classmethod
    def capabilities(cls) -> Capabilities:
        return cls._CAPABILITIES

    @classmethod
    def supported_calls(cls) -> frozenset[type[FlowToolCall]]:
        return cls._SUPPORTED_CALLS

    def sandbox_count(self) -> int:
        return len(self._open_handles)

    async def open(
        self, spec: BackendSandboxSpec | None = None
    ) -> BackendSandbox:
        working_dir = (
            spec.working_dir
            if spec is not None and spec.working_dir is not None
            else tempfile.mkdtemp(prefix="rath-local-")
        )
        await anyio.Path(working_dir).mkdir(parents=True, exist_ok=True)
        sandbox = BackendSandbox(backend=self, handle=working_dir, spec=spec)
        self._open_handles.add(working_dir)
        return sandbox

    async def close(self, sandbox: BackendSandbox) -> None:
        if sandbox.closed:
            return
        self._open_handles.discard(sandbox.handle)
        sandbox.closed = True
        # Best-effort cleanup. ignore_errors=True keeps close idempotent even
        # when the directory is already gone or holds locked files on Windows.
        await anyio.to_thread.run_sync(
            lambda: shutil.rmtree(sandbox.handle, ignore_errors=True)
        )

    async def dispatch(
        self, sandbox: BackendSandbox, call: FlowToolCall
    ) -> ToolResult | bool:
        if sandbox.closed:
            raise BackendSandboxClosed(sandbox.handle)
        match call:
            case FlowToolCommandRun():
                return await self._command_run(sandbox, call)
            case FlowToolFilesRead():
                return await self._files_read(sandbox, call)
            case FlowToolFilesWrite():
                return await self._files_write(sandbox, call)
            case FlowToolFilesList():
                return await self._files_list(sandbox, call)
            case FlowToolFilesExists():
                return await self._files_exists(sandbox, call)
            case FlowToolCodeRun():
                return await self._code_run(sandbox, call)
            case _:
                raise UnsupportedFlowToolCall(type(call), self.name)

    # ------------------------------------------------------------------ helpers

    def _resolve(self, sandbox: BackendSandbox, path: str) -> anyio.Path:
        """Join ``path`` with the sandbox working dir if it is relative."""
        p = anyio.Path(path)
        if p.is_absolute():
            return p
        return anyio.Path(sandbox.handle) / path

    async def _command_run(
        self, sandbox: BackendSandbox, call: FlowToolCommandRun
    ) -> CommandResult:
        cwd = (
            self._resolve(sandbox, call.cwd)
            if call.cwd
            else anyio.Path(sandbox.handle)
        )
        # Merge ``call.env`` over the parent process env so platform vars
        # like PATH stay available; pass an empty dict to actually clear.
        env_arg: dict[str, str] | None = None
        if call.env is not None:
            env_arg = {**os.environ, **call.env}
        start = time.perf_counter()
        with _maybe_timeout(call.timeout):
            proc = await anyio.run_process(
                call.cmd,
                input=call.stdin,
                cwd=str(cwd),
                env=env_arg,
                check=False,
            )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return CommandResult(
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            elapsed_ms=elapsed_ms,
        )

    async def _files_read(
        self, sandbox: BackendSandbox, call: FlowToolFilesRead
    ) -> FileContent:
        p = self._resolve(sandbox, call.path)
        if call.encoding is None:
            return FileContent(data=await p.read_bytes())
        return FileContent(data=await p.read_text(encoding=call.encoding))

    async def _files_write(
        self, sandbox: BackendSandbox, call: FlowToolFilesWrite
    ) -> FileWriteResult:
        p = self._resolve(sandbox, call.path)
        await p.parent.mkdir(parents=True, exist_ok=True)
        payload = call.data.encode("utf-8") if isinstance(call.data, str) else call.data
        await p.write_bytes(payload)
        # chmod is a best-effort op; on Windows only the read-only bit is
        # honoured, which matches stdlib behaviour.
        with contextlib.suppress(OSError):
            await p.chmod(call.mode)
        return FileWriteResult(bytes_written=len(payload))

    async def _files_list(
        self, sandbox: BackendSandbox, call: FlowToolFilesList
    ) -> FileEntries:
        p = self._resolve(sandbox, call.path)
        entries: list[FileEntry] = []
        async for child in p.iterdir():
            entries.append(
                FileEntry(
                    name=child.name,
                    path=str(child),
                    is_dir=await child.is_dir(),
                )
            )
        entries.sort(key=lambda e: e.name)
        return FileEntries(entries=tuple(entries))

    async def _files_exists(
        self, sandbox: BackendSandbox, call: FlowToolFilesExists
    ) -> bool:
        p = self._resolve(sandbox, call.path)
        return await p.exists()

    async def _code_run(
        self, sandbox: BackendSandbox, call: FlowToolCodeRun
    ) -> CodeResult:
        if call.language != "python":
            raise UnsupportedFlowToolCall(type(call), self.name)
        work = anyio.Path(sandbox.handle)
        tmp = work / f".rath_code_{uuid.uuid4().hex}.py"
        await tmp.write_text(call.code, encoding="utf-8")
        try:
            with _maybe_timeout(call.timeout):
                proc = await anyio.run_process(
                    [sys.executable, str(tmp)],
                    cwd=str(work),
                    check=False,
                )
        finally:
            with contextlib.suppress(FileNotFoundError, OSError):
                await tmp.unlink()
        error = (
            proc.stderr.decode("utf-8", errors="replace")
            if proc.returncode != 0
            else None
        )
        return CodeResult(
            text=None,
            stdout=proc.stdout,
            stderr=proc.stderr,
            error=error,
        )
