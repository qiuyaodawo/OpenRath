#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is not on PATH (install from https://docs.astral.sh/uv/)" >&2
  exit 1
fi

echo "syncing dev dependency group..."
uv sync --group dev

echo "running ruff..."
uv run ruff check src tests example
uv run ruff format --check src tests example

echo "running mypy..."
uv run mypy --no-incremental src

echo "running pytest..."
uv run pytest "$@"
