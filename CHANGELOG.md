# Changelog

All notable changes to OpenRath will be documented in this file.

OpenRath uses human-readable release notes. Until the project reaches its first
public release, this changelog records repository-level milestones rather than
stable API guarantees.

## Unreleased

### Added

- Initialized the Python package with `uv`.
- Added pytest, flake8, and mypy configuration for local quality checks.
- Added the `rath` source package under `src/rath`.
- Added BSD 3-Clause license and contributor documentation.
- **`rath.backend` Phase 1**: core abstractions and the `LocalBackend` adapter.
  - Value-object tool calls: `CommandRun`, `FilesRead`, `FilesWrite`,
    `FilesList`, `FilesExists`, `CodeRun`.
  - Value-object tool results: `CommandResult`, `FileContent`, `FileEntries`,
    `FileWriteResult`, `CodeResult`. `FilesExists` returns a bare `bool`.
  - `Backend` ABC with a single dispatch surface
    `dispatch(sandbox, call) -> ToolResult | bool`, plus class-level
    `is_available` / `capabilities` / `supported_calls` and instance-level
    `sandbox_count` / `open` / `close`.
  - `Sandbox` runtime handle with async context manager support.
  - `Capabilities` + `IsolationLevel` for static backend description.
  - Backend registry: `register`, `get`, `get_class`, `list_names`,
    `is_available`, `preferred`, `set_default`, `current`.
  - Error hierarchy under `BackendError`: `UnsupportedToolCall`,
    `SandboxClosed`, `BackendNotFound`.
  - `LocalBackend`: always-available host-side subprocess + filesystem
    backend with a per-sandbox working directory.
- Test suite: 146 tests covering unit value semantics, registry, errors,
  capabilities; LocalBackend-specific behaviour; and a conformance suite
  parametrized over backends covering lifecycle, command run, files, code
  run, concurrency, and cancellation.
- **`rath.backend` Phase 2**: optional concurrency primitives.
  - `Stream`: per-sandbox FIFO queue of tool-call operations, implemented as
    a backend-agnostic anyio worker task; multiple streams over the same
    sandbox run concurrently. `Stream` is itself an async context manager.
  - `Event`: cross-stream synchronization marker; `record_event` /
    `wait_event` / `wait_stream` express happens-before ordering.
  - `Future`: awaitable handle returned by `Stream.submit`; propagates
    exceptions raised by dispatch.
  - `Sandbox.stream(buffer=0)`: convenience factory; ``buffer=0`` means an
    unbounded queue, positive integers apply backpressure.
  - The `flags()` ContextProp planned for `rath.backends.opensandbox` was
    deferred: there is no consumer yet, and adding it now would violate the
    "keep it simple" directive.
- 15 additional tests for streams: unit (FIFO, parallel streams,
  record_event / wait_event / wait_stream / synchronize / query, future
  exception propagation, bounded buffer) plus a parametrized conformance
  suite that exercises the same semantics on every available backend.
- **`rath.backend` Phase 3**: `OpenSandboxBackend` adapter for the Alibaba
  OpenSandbox runtime.
  - Maps every Phase 1 tool call to the OpenSandbox SDK: `CommandRun` to
    `Sandbox.commands.run` (with `RunCommandOpts`), `FilesRead` to
    `read_file` / `read_bytes`, `FilesWrite` to `write_file`, `FilesList`
    to `Filesystem.search` (glob `*`), `FilesExists` to
    `Filesystem.get_file_info`, `CodeRun` to `CodeInterpreter.codes.run`.
  - Translates SDK "not found" errors into stdlib `FileNotFoundError` so
    the conformance suite stays portable.
  - Resolves relative tool-call paths under a sandbox-internal
    `/workspace` root, and uses that as the default cwd for `CommandRun`.
    This keeps relative-path conformance behaviour aligned with
    LocalBackend.
  - `Sandbox.commands.run` has no stdin parameter, so `CommandRun(stdin=...)`
    raises `UnsupportedToolCall`; the conformance test for stdin skips
    automatically when running on this backend.
- Tests: 11 backend-specific tests in `tests/backends/test_opensandbox.py`
  plus the existing conformance suite parametrized with `opensandbox`. All
  OpenSandbox-touching tests are gated on `tests/conftest.opensandbox_real`,
  a `pytest.mark.skipif` that probes ``localhost:8080`` for a live
  ``opensandbox-server``. With the server down the suite reports 161
  passed and 40 skipped; running the server makes those 40 cases attempt
  real Docker-backed sandbox creation.

### Fixed

- `OpenSandboxBackend`: define `_maybe_timeout` using `anyio.fail_after` and
  wrap `codes.run` the same way as `commands.run`, so tool calls with
  `timeout=` surface `TimeoutError` on the client and no longer raise
  `NameError` during dispatch.
- `OpenSandboxBackend`: default `Sandbox.create` `entrypoint` to
  ``/opt/opensandbox/code-interpreter.sh`` for `opensandbox/code-interpreter`
  images so the in-container interpreter endpoint starts reliably.
- Conformance command tests now take a `python_cmd` fixture: host
  `sys.executable` for `local`, ``python3`` on `$PATH` inside OpenSandbox
  containers (replacing `sys.executable` everywhere, which is not valid
  Linux paths when the test runner is Windows).

### Notes

- Scope is intentionally limited to the backend layer. `rath.Session` and
  `rath.Agent` are not implemented yet.
- No mocks and no smoke tests in the test suite (conformance targets real
  subprocesses, filesystem, and optional live OpenSandbox).
- Running the OpenSandbox tests against a real server requires a working
  Docker daemon plus the OpenSandbox container images
  (`opensandbox/code-interpreter:v1.0.2` and `opensandbox/execd:v1.0.13`).
  Bootstrap with `uvx opensandbox-server init-config ~/.sandbox.toml --example docker`
  followed by `OPENSANDBOX_INSECURE_SERVER=YES uvx opensandbox-server`.
