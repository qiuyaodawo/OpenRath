"""Host-process backend: subprocesses and filesystem under a temp working directory.

Always available. Relative paths in tool calls are resolved against the sandbox
working directory; absolute paths pass through unchanged.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import ClassVar

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

    def open(
        self, spec: BackendSandboxSpec | None = None
    ) -> BackendSandbox:
        working_dir = (
            spec.working_dir
            if spec is not None and spec.working_dir is not None
            else tempfile.mkdtemp(prefix="rath-local-")
        )
        Path(working_dir).mkdir(parents=True, exist_ok=True)
        sandbox = BackendSandbox(backend=self, handle=working_dir, spec=spec)
        self._open_handles.add(working_dir)
        return sandbox

    def close(self, sandbox: BackendSandbox) -> None:
        if sandbox.closed:
            return
        self._open_handles.discard(sandbox.handle)
        sandbox.closed = True
        shutil.rmtree(sandbox.handle, ignore_errors=True)

    def dispatch(
        self, sandbox: BackendSandbox, call: BackendTool
    ) -> ToolResult | bool:
        if sandbox.closed:
            raise BackendSandboxClosed(sandbox.handle)
        match call:
            case BackendToolCommandRun():
                return self._command_run(sandbox, call)
            case BackendToolFilesRead():
                return self._files_read(sandbox, call)
            case BackendToolFilesWrite():
                return self._files_write(sandbox, call)
            case BackendToolFilesList():
                return self._files_list(sandbox, call)
            case BackendToolFilesExists():
                return self._files_exists(sandbox, call)
            case BackendToolCodeRun():
                return self._code_run(sandbox, call)
            case _:
                raise UnsupportedBackendTool(type(call), self.name)

    def _resolve(self, sandbox: BackendSandbox, path: str) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p
        return Path(sandbox.handle) / path

    def _command_run(
        self, sandbox: BackendSandbox, call: BackendToolCommandRun
    ) -> CommandResult:
        cwd = (
            self._resolve(sandbox, call.cwd)
            if call.cwd
            else Path(sandbox.handle)
        )
        env_arg: dict[str, str] | None = None
        if call.env is not None:
            env_arg = {**os.environ, **call.env}
        start = time.perf_counter()
        run_kw: dict = dict(
            args=call.cmd,
            input=call.stdin,
            cwd=str(cwd),
            env=env_arg,
            capture_output=True,
        )
        if call.timeout is not None:
            run_kw["timeout"] = call.timeout
        try:
            proc = subprocess.run(**run_kw)  # type: ignore[arg-type]
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError from exc
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return CommandResult(
            exit_code=int(proc.returncode),
            stdout=proc.stdout if proc.stdout is not None else b"",
            stderr=proc.stderr if proc.stderr is not None else b"",
            elapsed_ms=elapsed_ms,
        )

    def _files_read(
        self, sandbox: BackendSandbox, call: BackendToolFilesRead
    ) -> FileContent:
        p = self._resolve(sandbox, call.path)
        if call.encoding is None:
            return FileContent(data=p.read_bytes())
        return FileContent(data=p.read_text(encoding=call.encoding))

    def _files_write(
        self, sandbox: BackendSandbox, call: BackendToolFilesWrite
    ) -> FileWriteResult:
        p = self._resolve(sandbox, call.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload_bytes = (
            call.data.encode("utf-8") if isinstance(call.data, str) else call.data
        )
        p.write_bytes(payload_bytes)
        with contextlib.suppress(OSError):
            p.chmod(call.mode)
        return FileWriteResult(bytes_written=len(payload_bytes))

    def _files_list(
        self, sandbox: BackendSandbox, call: BackendToolFilesList
    ) -> FileEntries:
        p = self._resolve(sandbox, call.path)
        entries = [
            FileEntry(
                name=child.name,
                path=str(child),
                is_dir=child.is_dir(),
            )
            for child in p.iterdir()
        ]
        entries.sort(key=lambda e: e.name)
        return FileEntries(entries=tuple(entries))

    def _files_exists(
        self, sandbox: BackendSandbox, call: BackendToolFilesExists
    ) -> bool:
        return self._resolve(sandbox, call.path).exists()

    def _code_run(
        self, sandbox: BackendSandbox, call: BackendToolCodeRun
    ) -> CodeResult:
        if call.language != "python":
            raise UnsupportedBackendTool(type(call), self.name)
        work = Path(sandbox.handle)
        tmp = work / f".rath_code_{uuid.uuid4().hex}.py"
        tmp.write_text(call.code, encoding="utf-8")
        proc: subprocess.CompletedProcess[bytes] | None = None
        try:
            run_kw: dict = dict(
                args=[sys.executable, str(tmp)],
                cwd=str(work),
                capture_output=True,
            )
            if call.timeout is not None:
                run_kw["timeout"] = call.timeout
            proc = subprocess.run(**run_kw)  # type: ignore[arg-type]
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError from exc
        finally:
            with contextlib.suppress(FileNotFoundError, OSError):
                tmp.unlink()
        assert proc is not None
        error = (
            proc.stderr.decode("utf-8", errors="replace")
            if proc.returncode != 0
            else None
        )
        return CodeResult(
            text=None,
            stdout=proc.stdout if proc.stdout is not None else b"",
            stderr=proc.stderr if proc.stderr is not None else b"",
            error=error,
        )
