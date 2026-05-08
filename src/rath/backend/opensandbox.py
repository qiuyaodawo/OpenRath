"""OpenSandbox-backed runtime: remote containers via the ``opensandbox`` SDK.

Needs optional ``opensandbox`` / ``code_interpreter`` packages and a reachable
``opensandbox-server`` (env ``OPEN_SANDBOX_DOMAIN`` / ``OPEN_SANDBOX_API_KEY``,
legacy ``OPENSANDBOX_DOMAIN``, or ``~/.sandbox.toml``).

The SDK is async; this backend runs it on a dedicated background event loop and
exposes **blocking** :meth:`open` / :meth:`close` / :meth:`dispatch` to callers.
"""

from __future__ import annotations

import asyncio
import os
import shlex
import stat as stat_module
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from rath.backend.abc import Backend, BackendSandbox, BackendSandboxSpec
from rath.backend.capabilities import Capabilities, IsolationLevel
from rath.backend.dedicated_loop import shared_opensandbox_loop
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

try:
    from opensandbox import Sandbox as _OSBSandbox
    from opensandbox.exceptions import SandboxException
    from opensandbox.models.execd import RunCommandOpts
    from opensandbox.models.filesystem import SearchEntry

    _SDK_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when extra is missing
    _SDK_AVAILABLE = False
    SandboxException = Exception  # type: ignore[assignment, misc]

try:
    from code_interpreter import CodeInterpreter

    _CI_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when extra is missing
    _CI_AVAILABLE = False

_SUPPORTED_LANGUAGES: frozenset[str] = frozenset(
    {"bash", "go", "java", "javascript", "python", "typescript"}
)

if TYPE_CHECKING:
    from opensandbox import Sandbox as _OSBSandboxT


async def _await_maybe_timeout(awaitable, timeout: float | None):
    if timeout is None:
        return await awaitable
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise TimeoutError from exc


@register("opensandbox")
class OpenSandboxBackend(Backend):
    """Map :class:`~rath.backend.tool_types.BackendTool` payloads to OpenSandbox APIs.

    * ``BackendToolCommandRun`` → ``commands.run`` (no stdin passthrough).
    * File tools → ``files.read_*``, ``files.write_file``, ``files.search``, ``files.get_file_info``.
    * ``BackendToolCodeRun`` → ``CodeInterpreter.codes.run``.

    Default image/entrypoint target ``opensandbox/code-interpreter``; relative paths use
    :attr:`_SANDBOX_ROOT` inside the container.
    """

    name: ClassVar[str] = "opensandbox"

    _DEFAULT_IMAGE: ClassVar[str] = "opensandbox/code-interpreter:v1.0.2"
    _DEFAULT_TIMEOUT: ClassVar[timedelta] = timedelta(minutes=10)
    _DEFAULT_ENTRYPOINT: ClassVar[tuple[str, ...]] = (
        "/opt/opensandbox/code-interpreter.sh",
    )
    _SANDBOX_ROOT: ClassVar[str] = "/workspace"

    _CAPABILITIES: ClassVar[Capabilities] = Capabilities(
        isolation=IsolationLevel.CONTAINER,
        supports_command=True,
        supports_filesystem=True,
        supports_code_interpreter=True,
        cold_start_ms_p50=None,
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
        self._natives: dict[str, "_OSBSandboxT"] = {}
        self._runner = shared_opensandbox_loop()

    @classmethod
    def is_available(cls) -> bool:
        """True when optional deps load and env or ``~/.sandbox.toml`` configures a server (no RPC)."""
        if not (_SDK_AVAILABLE and _CI_AVAILABLE):
            return False
        if os.environ.get("OPEN_SANDBOX_DOMAIN") or os.environ.get(
            "OPENSANDBOX_DOMAIN",
        ):
            return True
        return Path.home().joinpath(".sandbox.toml").exists()

    @classmethod
    def capabilities(cls) -> Capabilities:
        return cls._CAPABILITIES

    @classmethod
    def supported_calls(cls) -> frozenset[type[BackendTool]]:
        return cls._SUPPORTED_CALLS

    def sandbox_count(self) -> int:
        return len(self._natives)

    def open(
        self, spec: BackendSandboxSpec | None = None
    ) -> BackendSandbox:
        if not _SDK_AVAILABLE:  # pragma: no cover - guarded by is_available
            raise RuntimeError(
                "opensandbox SDK is not installed; "
                "install with `pip install rath[opensandbox]`"
            )
        image = spec.image if spec is not None and spec.image else self._DEFAULT_IMAGE
        timeout = (
            spec.timeout
            if spec is not None and spec.timeout is not None
            else self._DEFAULT_TIMEOUT
        )
        env = dict(spec.env) if spec is not None and spec.env is not None else None
        entrypoint = (
            list(spec.entrypoint)
            if spec is not None and spec.entrypoint is not None
            else list(self._DEFAULT_ENTRYPOINT)
        )
        return self._runner.run(
            self._open_coro(image, timeout, env, entrypoint, spec)
        )

    async def _open_coro(
        self,
        image: str,
        timeout: timedelta,
        env: dict[str, str] | None,
        entrypoint: list[str],
        spec: BackendSandboxSpec | None,
    ) -> BackendSandbox:
        native = await _OSBSandbox.create(
            image,
            timeout=timeout,
            env=env,
            entrypoint=entrypoint,
        )
        await native.commands.run(f"mkdir -p {shlex.quote(self._SANDBOX_ROOT)}")
        self._natives[native.id] = native
        return BackendSandbox(backend=self, handle=native.id, spec=spec)

    def close(self, sandbox: BackendSandbox) -> None:
        if sandbox.closed:
            return
        sandbox.closed = True
        native = self._natives.pop(sandbox.handle, None)
        if native is not None:
            self._runner.run(self._close_coro(native))

    async def _close_coro(self, native: "_OSBSandboxT") -> None:
        await native.kill()
        await native.close()

    def dispatch(
        self, sandbox: BackendSandbox, call: BackendTool
    ) -> ToolResult | bool:
        if sandbox.closed:
            raise BackendSandboxClosed(sandbox.handle)
        native = self._natives.get(sandbox.handle)
        if native is None:
            raise BackendSandboxClosed(sandbox.handle)
        return self._runner.run(self._dispatch_coro(native, call))

    async def _dispatch_coro(
        self, native: "_OSBSandboxT", call: BackendTool
    ) -> ToolResult | bool:
        match call:
            case BackendToolCommandRun():
                return await self._command_run(native, call)
            case BackendToolFilesRead():
                return await self._files_read(native, call)
            case BackendToolFilesWrite():
                return await self._files_write(native, call)
            case BackendToolFilesList():
                return await self._files_list(native, call)
            case BackendToolFilesExists():
                return await self._files_exists(native, call)
            case BackendToolCodeRun():
                return await self._code_run(native, call)
            case _:
                raise UnsupportedBackendTool(type(call), self.name)

    def _resolve(self, path: str) -> str:
        """Resolve a tool-call path: absolute paths pass through, relative
        paths are joined with the sandbox root."""
        if path.startswith("/"):
            return path
        if path in (".", "./"):
            return self._SANDBOX_ROOT
        if path.startswith("./"):
            path = path[2:]
        return f"{self._SANDBOX_ROOT}/{path}"

    async def _command_run(
        self, native: "_OSBSandboxT", call: BackendToolCommandRun
    ) -> CommandResult:
        """``commands.run`` has no stdin; non-``None`` ``call.stdin`` is rejected."""
        if call.stdin is not None:
            raise UnsupportedBackendTool(type(call), self.name)
        cmd_str = (
            call.cmd
            if isinstance(call.cmd, str)
            else _join_cmd(call.cmd)
        )
        opts = RunCommandOpts(
            working_directory=(
                self._resolve(call.cwd) if call.cwd is not None else self._SANDBOX_ROOT
            ),
            timeout=(
                timedelta(seconds=call.timeout) if call.timeout is not None else None
            ),
            envs=dict(call.env) if call.env is not None else None,
        )
        execution = await _await_maybe_timeout(
            native.commands.run(cmd_str, opts=opts),
            call.timeout,
        )
        stdout = "".join(m.text for m in execution.logs.stdout).encode("utf-8")
        stderr = "".join(m.text for m in execution.logs.stderr).encode("utf-8")
        elapsed_ms = (
            float(execution.complete.execution_time_in_millis)
            if execution.complete is not None
            else 0.0
        )
        return CommandResult(
            exit_code=execution.exit_code if execution.exit_code is not None else 0,
            stdout=stdout,
            stderr=stderr,
            elapsed_ms=elapsed_ms,
        )

    async def _files_read(
        self, native: "_OSBSandboxT", call: BackendToolFilesRead
    ) -> FileContent:
        path = self._resolve(call.path)
        try:
            if call.encoding is None:
                return FileContent(data=await native.files.read_bytes(path))
            return FileContent(
                data=await native.files.read_file(path, encoding=call.encoding)
            )
        except SandboxException as exc:
            msg = str(exc).lower()
            if "not found" in msg or "no such file" in msg or "404" in msg:
                raise FileNotFoundError(path) from exc
            raise

    async def _files_write(
        self, native: "_OSBSandboxT", call: BackendToolFilesWrite
    ) -> FileWriteResult:
        path = self._resolve(call.path)
        await native.files.write_file(path, call.data, mode=call.mode)
        payload = (
            call.data.encode("utf-8") if isinstance(call.data, str) else call.data
        )
        return FileWriteResult(bytes_written=len(payload))

    async def _files_list(
        self, native: "_OSBSandboxT", call: BackendToolFilesList
    ) -> FileEntries:
        path = self._resolve(call.path)
        infos = await native.files.search(SearchEntry(path=path, pattern="*"))
        entries = [
            FileEntry(
                name=Path(info.path).name,
                path=info.path,
                is_dir=stat_module.S_ISDIR(info.mode),
            )
            for info in infos
        ]
        entries.sort(key=lambda e: e.name)
        return FileEntries(entries=tuple(entries))

    async def _files_exists(
        self, native: "_OSBSandboxT", call: BackendToolFilesExists
    ) -> bool:
        path = self._resolve(call.path)
        try:
            infos = await native.files.get_file_info([path])
        except SandboxException:
            return False
        return path in infos

    async def _code_run(
        self, native: "_OSBSandboxT", call: BackendToolCodeRun
    ) -> CodeResult:
        if not _CI_AVAILABLE:  # pragma: no cover - guarded by is_available
            raise RuntimeError(
                "code-interpreter SDK is not installed; "
                "install with `pip install rath[opensandbox]`"
            )
        if call.language not in _SUPPORTED_LANGUAGES:
            raise UnsupportedBackendTool(type(call), self.name)
        ci = await CodeInterpreter.create(native)
        execution = await _await_maybe_timeout(
            ci.codes.run(call.code, language=call.language),
            call.timeout,
        )
        stdout = "".join(m.text for m in execution.logs.stdout).encode("utf-8")
        stderr = "".join(m.text for m in execution.logs.stderr).encode("utf-8")
        text = execution.result[0].text if execution.result else None
        error = execution.error.value if execution.error is not None else None
        return CodeResult(text=text, stdout=stdout, stderr=stderr, error=error)


def _join_cmd(cmd: Sequence[str]) -> str:
    """Serialize a list-form command into a shell-safe string."""
    return shlex.join(cmd)
