#!/usr/bin/env bash
# Sanity-check optional OpenSandbox: Python extra imports and server /health endpoint.
# Uses OPEN_SANDBOX_DOMAIN from the environment (default 127.0.0.1:8080).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

DOMAIN="${OPEN_SANDBOX_DOMAIN:-127.0.0.1:8080}"
BASE_URL="http://${DOMAIN}"
HEALTH_URL="${BASE_URL}/health"

echo "repo root: ${ROOT_DIR}"
echo "OpenSandbox API base: ${BASE_URL}"

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is not on PATH (https://docs.astral.sh/uv/)" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "error: curl is not on PATH" >&2
  exit 1
fi

if [[ -f .sandbox.toml ]]; then
  echo "found .sandbox.toml (server config; client uses OPEN_SANDBOX_DOMAIN)"
else
  echo "note: no .sandbox.toml in repo root (optional for local server)"
fi

echo ""
echo "[1/2] optional dependency: opensandbox (uv --extra opensandbox)"
if ! uv run --extra opensandbox python -c "import opensandbox"; then
  echo "error: cannot import opensandbox. Try: uv sync --extra opensandbox" >&2
  exit 1
fi
echo "      ok"

echo ""
echo "[2/2] HTTP GET ${HEALTH_URL}"
BODY_FILE="$(mktemp)"
trap 'rm -f "${BODY_FILE}"' EXIT
HTTP_CODE="$(
  curl -sS -o "${BODY_FILE}" -w "%{http_code}" \
    --connect-timeout 5 --max-time 15 \
    "${HEALTH_URL}" || true
)"
if [[ "${HTTP_CODE}" != "200" ]]; then
  echo "error: expected HTTP 200 from /health, got ${HTTP_CODE:-<no response>}" >&2
  if [[ -s "${BODY_FILE}" ]]; then
    echo "body:" >&2
    head -c 500 "${BODY_FILE}" >&2 || true
    echo >&2
  fi
  echo "hint: start the server with scripts/launch_opensandbox.sh, or set OPEN_SANDBOX_DOMAIN to a reachable host:port." >&2
  exit 1
fi
echo "      ok (${HTTP_CODE})"
if [[ -s "${BODY_FILE}" ]]; then
  head -c 200 "${BODY_FILE}"
  echo ""
fi

echo ""
echo "OpenSandbox check passed."
