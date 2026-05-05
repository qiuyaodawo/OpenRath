"""OpenSandboxBackend: dispatch tool calls into a real OpenSandbox runtime.

This adapter requires the optional ``opensandbox`` and
``opensandbox-code-interpreter`` packages, plus a running ``opensandbox-server``
that the SDK can reach via its standard ConnectionConfig discovery (the
``OPENSANDBOX_DOMAIN`` environment variable or the user-level ``~/.sandbox.toml``
config file).

Mapping summary:

* ``CommandRun`` -> ``Sandbox.commands.run`` (with stdin currently unsupported)
* ``FilesRead``  -> ``Sandbox.files.read_file`` / ``read_bytes``
* ``FilesWrite`` -> ``Sandbox.files.write_file``
* ``FilesList``  -> ``Sandbox.files.search`` (glob ``"*"`` over the path)
* ``FilesExists``-> ``Sandbox.files.get_file_info`` (membership check)
* ``CodeRun``    -> ``CodeInterpreter.create(sandbox).codes.run``

The plan's documented ``files.list`` / ``files.exists`` fallback paths via
``commands.run("ls ...")`` / ``commands.run("test -e ...")`` are unnecessary
with the installed SDK, which exposes both operations natively.
"""

from __future__ import annotations

import os
import shlex
import stat as stat_module
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from rath.backend._abc import Backend, Sandbox, SandboxSpec
from rath.backend._calls import (
    CodeRun,
    CommandRun,
    FilesExists,
    FilesList,
    FilesRead,
    FilesWrite,
    ToolCall,
)
from rath.backend._capabilities import Capabilities, IsolationLevel
from rath.backend._errors import SandboxClosed, UnsupportedToolCall
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

# Optional dependency: import lazily so that ``rath.backend`` stays importable
# without ``opensandbox`` being installed. ``is_available`` returns ``False``
# when the SDK is missing, so users see a clear error before any dispatch.
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

# Mirrors ``code_interpreter.SupportedLanguage`` so we can validate without
# importing the optional dep at type-check time. Keep in sync if the SDK adds
# new languages.
_SUPPORTED_LANGUAGES: frozenset[str] = frozenset(
    {"bash", "go", "java", "javascript", "python", "typescript"}
)

if TYPE_CHECKING:
    from opensandbox import Sandbox as _OSBSandboxT


@register("opensandbox")
class OpenSandboxBackend(Backend):
    """Dispatch tool calls into an OpenSandbox container runtime."""

    name: ClassVar[str] = "opensandbox"

    _DEFAULT_IMAGE: ClassVar[str] = "opensandbox/code-interpreter:v1.0.2"
    _DEFAULT_TIMEOUT: ClassVar[timedelta] = timedelta(minutes=10)
    # Sandbox-internal directory used as the implicit root for relative paths
    # in tool calls and as the default cwd for ``CommandRun``. Conformance
    # tests assume that relative paths in one tool call resolve to the same
    # location as the cwd of a sibling ``CommandRun``; this default makes
    # that hold.
    _SANDBOX_ROOT: ClassVar[str] = "/workspace"

    _CAPABILITIES: ClassVar[Capabilities] = Capabilities(
        isolation=IsolationLevel.CONTAINER,
        supports_command=True,
        supports_filesystem=True,
        supports_code_interpreter=True,
        cold_start_ms_p50=None,
        max_sandboxes=None,
    )

    _SUPPORTED_CALLS: ClassVar[frozenset[type[ToolCall]]] = frozenset(
        {CommandRun, FilesRead, FilesWrite, FilesList, FilesExists, CodeRun}
    )

    def __init__(self) -> None:
        self._natives: dict[str, "_OSBSandboxT"] = {}

    @classmethod
    def is_available(cls) -> bool:
        """Available when the SDK is importable and a connection target is set.

        Either ``OPENSANDBOX_DOMAIN`` is in the environment or the user has a
        ``~/.sandbox.toml`` config file. We never reach out over the network
        from this method; that is only attempted by an actual ``open()`` call.
        """
        if not (_SDK_AVAILABLE and _CI_AVAILABLE):
            return False
        if "OPENSANDBOX_DOMAIN" in os.environ:
            return True
        return Path.home().joinpath(".sandbox.toml").exists()

    @classmethod
    def capabilities(cls) -> Capabilities:
        return cls._CAPABILITIES

    @classmethod
    def supported_calls(cls) -> frozenset[type[ToolCall]]:
        return cls._SUPPORTED_CALLS

    def sandbox_count(self) -> int:
        return len(self._natives)

    async def open(self, spec: SandboxSpec | None = None) -> Sandbox:
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
            else None
        )
        native = await _OSBSandbox.create(
            image,
            timeout=timeout,
            env=env,
            entrypoint=entrypoint,
        )
        # Ensure the sandbox-internal root exists so relative paths resolve.
        await native.commands.run(f"mkdir -p {shlex.quote(self._SANDBOX_ROOT)}")
        self._natives[native.id] = native
        return Sandbox(backend=self, handle=native.id, spec=spec)

    async def close(self, sandbox: Sandbox) -> None:
        if sandbox.closed:
            return
        sandbox.closed = True
        native = self._natives.pop(sandbox.handle, None)
        if native is not None:
            await native.kill()
            await native.close()

    async def dispatch(
        self, sandbox: Sandbox, call: ToolCall
    ) -> ToolResult | bool:
        if sandbox.closed:
            raise SandboxClosed(sandbox.handle)
        native = self._natives.get(sandbox.handle)
        if native is None:
            raise SandboxClosed(sandbox.handle)
        match call:
            case CommandRun():
                return await self._command_run(native, call)
            case FilesRead():
                return await self._files_read(native, call)
            case FilesWrite():
                return await self._files_write(native, call)
            case FilesList():
                return await self._files_list(native, call)
            case FilesExists():
                return await self._files_exists(native, call)
            case CodeRun():
                return await self._code_run(native, call)
            case _:
                raise UnsupportedToolCall(type(call), self.name)

    # ------------------------------------------------------------------ helpers

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
        self, native: "_OSBSandboxT", call: CommandRun
    ) -> CommandResult:
        if call.stdin is not None:
            # OpenSandbox's commands.run does not have a stdin parameter; we
            # could shim via temp file + shell redirect but it is rarely
            # needed and would obscure the simple mapping.
            raise UnsupportedToolCall(type(call), self.name)
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
        execution = await native.commands.run(cmd_str, opts=opts)
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
        self, native: "_OSBSandboxT", call: FilesRead
    ) -> FileContent:
        path = self._resolve(call.path)
        try:
            if call.encoding is None:
                return FileContent(data=await native.files.read_bytes(path))
            return FileContent(
                data=await native.files.read_file(path, encoding=call.encoding)
            )
        except SandboxException as exc:
            # Translate "not found" SDK errors to the stdlib type that the
            # conformance suite already expects across backends.
            msg = str(exc).lower()
            if "not found" in msg or "no such file" in msg or "404" in msg:
                raise FileNotFoundError(path) from exc
            raise

    async def _files_write(
        self, native: "_OSBSandboxT", call: FilesWrite
    ) -> FileWriteResult:
        path = self._resolve(call.path)
        await native.files.write_file(path, call.data, mode=call.mode)
        payload = (
            call.data.encode("utf-8") if isinstance(call.data, str) else call.data
        )
        return FileWriteResult(bytes_written=len(payload))

    async def _files_list(
        self, native: "_OSBSandboxT", call: FilesList
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
        self, native: "_OSBSandboxT", call: FilesExists
    ) -> bool:
        path = self._resolve(call.path)
        try:
            infos = await native.files.get_file_info([path])
        except SandboxException:
            # The SDK may raise on missing paths; treat that as ``not exists``.
            return False
        return path in infos

    async def _code_run(
        self, native: "_OSBSandboxT", call: CodeRun
    ) -> CodeResult:
        if not _CI_AVAILABLE:  # pragma: no cover - guarded by is_available
            raise RuntimeError(
                "code-interpreter SDK is not installed; "
                "install with `pip install rath[opensandbox]`"
            )
        if call.language not in _SUPPORTED_LANGUAGES:
            raise UnsupportedToolCall(type(call), self.name)
        ci = await CodeInterpreter.create(native)
        execution = await ci.codes.run(call.code, language=call.language)
        stdout = "".join(m.text for m in execution.logs.stdout).encode("utf-8")
        stderr = "".join(m.text for m in execution.logs.stderr).encode("utf-8")
        text = execution.result[0].text if execution.result else None
        error = execution.error.value if execution.error is not None else None
        return CodeResult(text=text, stdout=stdout, stderr=stderr, error=error)


def _join_cmd(cmd: Sequence[str]) -> str:
    """Serialize a list-form command into a shell-safe string."""
    return shlex.join(cmd)
