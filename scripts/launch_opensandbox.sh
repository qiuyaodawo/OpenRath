#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONFIG_PATH="${ROOT_DIR}/.sandbox.toml"
# Packaged examples: docker | docker-zh | k8s | k8s-zh (default: docker).
INIT_EXAMPLE="${SANDBOX_INIT_EXAMPLE:-docker}"

cd "${ROOT_DIR}"

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker is not on PATH" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "error: Docker daemon is not running (or permission denied)." >&2
  exit 1
fi

echo "Checking Docker containers using OpenSandbox images..."
if docker ps -a --format '{{.Names}}	{{.Image}}	{{.Status}}' | grep -i opensandbox; then
  :
else
  echo "  (none found)"
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is not on PATH (install from https://docs.astral.sh/uv/)" >&2
  exit 1
fi

echo "syncing optional dependency opensandbox..."
uv sync --extra opensandbox

if [[ -f "${CONFIG_PATH}" ]]; then
  echo "using existing config: ${CONFIG_PATH}"
else
  echo "creating ${CONFIG_PATH} from packaged example: ${INIT_EXAMPLE}"
  uv run opensandbox-server init-config --example "${INIT_EXAMPLE}" "${CONFIG_PATH}"
fi

# Non-interactive dev start when api_key is not set (see .sandbox.toml header).
export OPENSANDBOX_INSECURE_SERVER="${OPENSANDBOX_INSECURE_SERVER:-YES}"

echo "starting opensandbox-server (Ctrl+C to stop)..."
exec uv run opensandbox-server --config "${CONFIG_PATH}"
