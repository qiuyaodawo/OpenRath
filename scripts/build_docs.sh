#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is not on PATH (install from https://docs.astral.sh/uv/)" >&2
  exit 1
fi

echo "syncing dev + docs dependency groups..."
uv sync --group dev --group docs

DOCS_SOURCE="${DOCS_SOURCE:-docs/source}"
DOCS_BUILD="${DOCS_BUILD:-docs/_build}"

echo "building HTML from ${DOCS_SOURCE} under ${DOCS_BUILD}/html ..."
uv run sphinx-build -M html "${DOCS_SOURCE}" "${DOCS_BUILD}" "$@"
