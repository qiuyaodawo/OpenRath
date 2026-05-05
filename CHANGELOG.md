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

### Notes

- Scope is intentionally limited to the backend layer. `rath.Session` and
  `rath.Agent` are not implemented yet.
- No mocks and no smoke tests in the test suite, per the design plan in
  `.claude/plans/rath-backend-design.md`.
