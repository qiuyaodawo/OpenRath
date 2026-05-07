"""Host-process backend: subprocesses and filesystem under a temp working directory.

Always available. Relative paths in tool calls are resolved against the sandbox
working directory; absolute paths pass through unchanged.
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

from rath.backend.abc import Backend, BackendSandbox, BackendSandboxSpec
from rath.backend.capabilities import Capabilities, IsolationLevel
from rath.backend.errors import BackendSandboxClosed, UnsupportedBackendTool
from rath.backend.registry import register
from rath.backend.results import (
    CodeResult,
    CommandResult,
    FileContent,
    FileEntries,
    FileEntry,
    FileWriteResult,
    ToolResult,
)
from rath.backend.tool_types import (
    BackendTool,
    BackendToolCodeRun,
    BackendToolCommandRun,
    BackendToolFilesExists,
    BackendToolFilesList,
    BackendToolFilesRead,
    BackendToolFilesWrite,
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

    _SUPPORTED_CALLS: ClassVar[frozenset[type[BackendTool]]] = frozenset(
        {
            BackendToolCommandRun,
            BackendToolFilesRead,
            BackendToolFilesWrite,
            BackendToolFilesList,
            BackendToolFilesExists,
            BackendToolCodeRun,
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
    def supported_calls(cls) -> frozenset[type[BackendTool]]:
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
        await anyio.to_thread.run_sync(
            lambda: shutil.rmtree(sandbox.handle, ignore_errors=True)
        )

    async def dispatch(
        self, sandbox: BackendSandbox, call: BackendTool
    ) -> ToolResult | bool:
        if sandbox.closed:
            raise BackendSandboxClosed(sandbox.handle)
        match call:
            case BackendToolCommandRun():
                return await self._command_run(sandbox, call)
            case BackendToolFilesRead():
                return await self._files_read(sandbox, call)
            case BackendToolFilesWrite():
                return await self._files_write(sandbox, call)
            case BackendToolFilesList():
                return await self._files_list(sandbox, call)
            case BackendToolFilesExists():
                return await self._files_exists(sandbox, call)
            case BackendToolCodeRun():
                return await self._code_run(sandbox, call)
            case _:
                raise UnsupportedBackendTool(type(call), self.name)

    def _resolve(self, sandbox: BackendSandbox, path: str) -> anyio.Path:
        """Join ``path`` with the sandbox working dir if it is relative."""
        p = anyio.Path(path)
        if p.is_absolute():
            return p
        return anyio.Path(sandbox.handle) / path

    async def _command_run(
        self, sandbox: BackendSandbox, call: BackendToolCommandRun
    ) -> CommandResult:
        """Merge ``call.env`` onto ``os.environ`` when ``call.env`` is not ``None``."""

        cwd = (
            self._resolve(sandbox, call.cwd)
            if call.cwd
            else anyio.Path(sandbox.handle)
        )
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
        self, sandbox: BackendSandbox, call: BackendToolFilesRead
    ) -> FileContent:
        p = self._resolve(sandbox, call.path)
        if call.encoding is None:
            return FileContent(data=await p.read_bytes())
        return FileContent(data=await p.read_text(encoding=call.encoding))

    async def _files_write(
        self, sandbox: BackendSandbox, call: BackendToolFilesWrite
    ) -> FileWriteResult:
        """Apply ``call.mode`` best-effort after write (Windows maps to read-only bit)."""

        p = self._resolve(sandbox, call.path)
        await p.parent.mkdir(parents=True, exist_ok=True)
        payload = call.data.encode("utf-8") if isinstance(call.data, str) else call.data
        await p.write_bytes(payload)
        with contextlib.suppress(OSError):
            await p.chmod(call.mode)
        return FileWriteResult(bytes_written=len(payload))

    async def _files_list(
        self, sandbox: BackendSandbox, call: BackendToolFilesList
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
        self, sandbox: BackendSandbox, call: BackendToolFilesExists
    ) -> bool:
        p = self._resolve(sandbox, call.path)
        return await p.exists()

    async def _code_run(
        self, sandbox: BackendSandbox, call: BackendToolCodeRun
    ) -> CodeResult:
        if call.language != "python":
            raise UnsupportedBackendTool(type(call), self.name)
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
