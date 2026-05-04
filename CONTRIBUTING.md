# Contributing to OpenRath

Thanks for your interest in contributing to OpenRath.

OpenRath is an open source, torch-like API framework for dynamic multi-agent
workflow. The project is currently early-stage, so design clarity matters more
than adding surface area quickly.

## Development Principles

- Keep the core session-based model small and explicit.
- Prefer composable APIs that feel familiar to PyTorch users.
- Treat sessions, effects, tool calls, and runtime boundaries as first-class
  concepts.
- Avoid adding production platform complexity before the core abstractions are
  stable.
- Keep changes focused. Large design shifts should be discussed before code is
  written.

## Development Setup

OpenRath uses `uv` for Python dependency and environment management.

```powershell
uv sync --dev
```

The project supports Python 3.10, 3.11, 3.12, and 3.13.

## Local Checks

Run these checks before opening a pull request:

```powershell
uv run flake8 src tests
uv run mypy --no-incremental
uv run pytest
```

## Project Layout

```text
src/rath/       Core Python package
tests/          Test suite
pyproject.toml  Package metadata and uv dependency groups
```

## Pull Request Guidelines

- Explain the motivation and scope of the change.
- Keep unrelated refactors out of feature or bugfix pull requests.
- Add tests for behavior changes.
- Update documentation when public behavior or setup steps change.
- Mention any trade-offs, limitations, or follow-up work clearly.

## Design Changes

For changes to core abstractions such as sessions, workflows, runtimes,
participants, tool calls, tracing, or graph semantics, please start with a
design discussion. A short design note is better than encoding major decisions
only in code.

## License

By contributing to OpenRath, you agree that your contributions will be licensed
under the BSD 3-Clause License.
