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
uv sync --dev

echo "running flake8..."
uv run flake8 src tests

echo "running mypy..."
uv run mypy --no-incremental

echo "running pytest..."
uv run pytest "$@"
