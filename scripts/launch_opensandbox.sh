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

if [[ -z "${DOCKER_HOST:-}" && -S "${HOME}/.colima/default/docker.sock" ]]; then
  export DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock"
  echo "using Colima Docker socket: ${DOCKER_HOST}"
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

python3 - "${CONFIG_PATH}" "${ROOT_DIR}" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
root_dir = str(Path(sys.argv[2]).resolve())
text = config_path.read_text()
needle = "allowed_host_paths = []"
if needle in text:
    config_path.write_text(
        text.replace(needle, f"allowed_host_paths = [{json.dumps(root_dir)}]", 1)
    )
    print(f"allowlisted OpenRath workspace for host bind: {root_dir}")
else:
    print("keeping existing storage.allowed_host_paths")
PY

# Non-interactive dev start when api_key is not set (see .sandbox.toml header).
export OPENSANDBOX_INSECURE_SERVER="${OPENSANDBOX_INSECURE_SERVER:-YES}"

echo "starting opensandbox-server (Ctrl+C to stop)..."
exec uv run opensandbox-server --config "${CONFIG_PATH}"
