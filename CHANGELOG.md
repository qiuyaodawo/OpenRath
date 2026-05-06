# Changelog

All notable changes to OpenRath will be documented in this file.

OpenRath uses human-readable release notes. Until the project reaches its first
public release, this changelog records repository-level milestones rather than
stable API guarantees.

## Unreleased

**Summary:** Refactor layout and naming: new ``rath.utils`` (env helpers), ``rath.backend`` split into ``core`` / ``results`` / ``stream`` / ``registry`` / ``adapters``, ``rath.flow.tool`` split into one module per call type, LLM entry renamed to ``RathOpenAIChatClient``. OpenSandbox discovery matches the official Python SDK (``OPEN_SANDBOX_DOMAIN`` / ``OPEN_SANDBOX_API_KEY``). Optional install is ``rath[opensandbox]`` (includes ``opensandbox-server``). Local server config ``.sandbox.toml`` is gitignored; generate it with ``opensandbox-server init-config``. Root ``tests/conftest.py`` loads project ``.env`` so pytest sees the same variables as the SDK.

### Testing

- Pytest markers **`opensandbox`**, **`live_llm`**, **`integration`** (``pytest.ini``)
  so quick runs can skip Docker-heavy, network-LLM, or full-stack suites:
  ``uv run pytest -m "not opensandbox"`` (~local + unit + conformance local),
  ``uv run pytest -m "not opensandbox and not live_llm"`` when you want no
  remote calls. Use ``uv run pytest -m "not integration"`` to skip stack tests
  in ``tests/integration/``. Full ``uv run pytest`` still runs everything (often several
  minutes when OpenSandbox parametrizations execute).

### Added — session plane / workflow MVP

- ``rath.session``: chunk tables, ``Session``, ``SessionLineage``, ``SessionRegistry``,
  async ``run_session_loop``, ``DefaultSessionLoopProvider`` (LLM via
  ``anyio.to_thread.run_sync``, sandbox via async ``BackendSandbox.dispatch``).
  Tool names and builders come from the global ``ToolTable``.

- ``rath.flow.workflow``: ``Workflow`` (registers assigned ``Agent``) and ``SingleAgent``.

- ``rath.flow.agent``: ``Agent`` bundle (system ``Session`` + ``SessionLoopProvider``).

- ``RathLLMMessage.tool_calls`` for multi-turn tool replay in chat requests.

- Integration tests: ``tests/integration/test_session_loop_real.py`` (markers
  ``integration``, ``opensandbox``, ``live_llm``).
### Breaking — ``rath.llm`` naming

- **Types** use the ``RathLLM*`` prefix (aligned with ``FlowTool*`` / ``Backend*``):
  ``LLMMessage`` → ``RathLLMMessage``, ``LLMChatRequest`` → ``RathLLMChatRequest``,
  ``LLMChatResponse`` → ``RathLLMChatResponse``, ``LLMSettings`` → ``RathLLMSettings``,
  and matching response / tool-call types (see ``rath.llm`` exports).
- **Settings loaders**: ``load_llm_settings`` → ``load_rath_llm_settings``;
  ``default_dotenv_path`` → ``rath_llm_default_dotenv_path`` (delegates to
  ``rath.utils.env.default_env_file_path``).
- **Client**: ``RathOpenAIChatAgent`` → ``RathOpenAIChatClient`` (implementation in
  ``src/rath/llm/_client.py``).

### Breaking — ``rath.backend`` layout

- Implementation is grouped under subpackages: ``rath.backend.core`` (ABCs,
  capabilities, errors), ``rath.backend.results``, ``rath.backend.stream``,
  ``rath.backend.registry``, and ``rath.backend.adapters`` (``local``,
  ``opensandbox``). The top-level ``rath.backend`` module still re-exports the
  same public names as before.
- **Deep imports** of removed flat modules (``rath.backend._registry``,
  ``rath.backend.local``, ``rath.backend.opensandbox``, etc.) must be updated
  to the new paths (e.g. ``rath.backend.adapters.local``).

### Breaking — ``rath.flow.tool`` and backend naming

- **Flow tool calls** (canonical definitions in ``rath.flow.tool`` only):
  ``ToolCall`` → ``FlowToolCall``; ``CommandRun`` → ``FlowToolCommandRun``;
  ``FilesRead`` / ``FilesWrite`` / ``FilesList`` / ``FilesExists`` →
  ``FlowToolFiles*``; ``CodeRun`` → ``FlowToolCodeRun``.
- **Functional factories** (``torch.nn.functional``-style):
  ``flow_tool_command_run``, ``flow_tool_files_read``, … in ``rath.flow.tool``.
- **Sandbox handle** (``rath.backend``): ``Sandbox`` → ``BackendSandbox``;
  ``SandboxSpec`` → ``BackendSandboxSpec``; ``SandboxClosed`` →
  ``BackendSandboxClosed``; ``UnsupportedToolCall`` → ``UnsupportedFlowToolCall``.
- **Packages**: ``rath.flow`` is a namespace stub; ``rath`` exposes ``flow`` and
  ``backend``. ``rath.backend._calls`` re-exports from ``rath.flow.tool`` for
  compatibility with deep imports.

### Added

- **`rath.utils`**: shared helpers for project-root discovery, optional
  ``load_dotenv``, and single-key ``read_dotenv_value`` (used by ``rath.llm`` and tests).
- **`rath.flow.tool`**: one module per tool kind (e.g. ``command_run.py``,
  ``files_read.py``) plus ``base.py``; factories unchanged on ``rath.flow.tool``.
- **`rath.llm`**: synchronous OpenAI-compatible chat via the official `openai` SDK.
  Use ``RathOpenAIChatClient.complete`` with frozen ``RathLLMChatRequest`` /
  ``RathLLMChatResponse``. Credentials load from `.env` / environment
  (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_DEFAULT_MODEL`). No Rath-level
  timeout or streaming in this phase. Dependencies: `openai`, `python-dotenv`.
- **`tests/llm`**: live-API integration tests only (require `OPENAI_API_KEY`; see
  `tests/llm/conftest.py`). Assertions tie the process key to the project `.env`
  file and exercise real completions — no HTTP mocks. The **full** `pytest` run
  therefore requires a key in `.env` or the environment.
- **OpenSandbox optional stack**: installing ``rath[opensandbox]`` pulls the Python SDK,
  code-interpreter helper, and **``opensandbox-server``** (same extra). Keep local
  ``.sandbox.toml`` out of version control (gitignored); create it with
  ``uv run opensandbox-server init-config .sandbox.toml --example docker`` (or use
  ``~/.sandbox.toml`` / ``SANDBOX_CONFIG_PATH`` per upstream docs). ``tests/conftest.py``
  loads project ``.env`` so ``OPEN_SANDBOX_*`` matches the SDK (see ``.env.example``).
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

- **OpenSandbox adapter**: ``is_available`` now treats ``OPEN_SANDBOX_DOMAIN`` (Python SDK) as a configured target, not only legacy ``OPENSANDBOX_DOMAIN``.
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
  Bootstrap with ``uv run opensandbox-server init-config ~/.sandbox.toml --example docker``
  (after ``uv sync --extra opensandbox``) followed by
  ``OPENSANDBOX_INSECURE_SERVER=YES uv run opensandbox-server`` when ``[server].api_key`` is unset.
