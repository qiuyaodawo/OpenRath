#!/usr/bin/env bash
# Launch a local OpenViking server (Docker) for memory-plane integration tests.
#
# Defaults:
#   image:     ghcr.io/volcengine/openviking:latest
#   API port:  1933 (host) -> 1933 (container)
#   UI port:   8020 (host) -> 8020 (container)
#   config:    ~/.openviking/ov.conf  (mounted as /app/.openviking)
#
# Environment overrides:
#   OPEN_VIKING_IMAGE        docker image tag
#   OPEN_VIKING_CONTAINER    container name (default: openrath-openviking)
#   OPEN_VIKING_API_PORT     host API port (default: 1933)
#   OPEN_VIKING_UI_PORT      host UI port (default: 8020)
#   OPEN_VIKING_DATA_DIR     host dir mounted as /app/.openviking (default: ~/.openviking)
#   OPEN_VIKING_ROOT_API_KEY required to bring up the server (auto-generated on first run if absent)
#
# OpenViking needs an embedding provider AND a VLM provider before it will boot.
# On first run we write ov.conf using credentials from env vars or
# ~/.openrath/config.json (see scripts/resolve_openviking_provider_env.py).
#   OPEN_VIKING_EMBEDDING_API_KEY   embedding provider api key
#   OPEN_VIKING_EMBEDDING_API_BASE  embedding api base
#   OPEN_VIKING_EMBEDDING_MODEL     embedding model name     (default: embedding-3)
#   OPEN_VIKING_EMBEDDING_DIMENSION embedding dim            (default: 2048)
#   OPEN_VIKING_VLM_API_KEY         vlm api key
#   OPEN_VIKING_VLM_API_BASE        vlm api base
#   OPEN_VIKING_VLM_MODEL           vlm model name           (default: glm-4.6v)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker is not on PATH" >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "error: Docker daemon is not running (or permission denied)." >&2
  exit 1
fi

IMAGE="${OPEN_VIKING_IMAGE:-ghcr.io/volcengine/openviking:latest}"
CONTAINER="${OPEN_VIKING_CONTAINER:-openrath-openviking}"
API_PORT="${OPEN_VIKING_API_PORT:-1933}"
UI_PORT="${OPEN_VIKING_UI_PORT:-8020}"
DATA_DIR="${OPEN_VIKING_DATA_DIR:-${HOME}/.openviking}"
CONFIG_PATH="${DATA_DIR}/ov.conf"

mkdir -p "${DATA_DIR}"

if [[ ! -f "${CONFIG_PATH}" ]]; then
  # shellcheck disable=SC2046
  eval "$(uv run python "${SCRIPT_DIR}/resolve_openviking_provider_env.py" | sed 's/^/export /')"
  EMB_API_KEY="${OPEN_VIKING_EMBEDDING_API_KEY}"
  EMB_API_BASE="${OPEN_VIKING_EMBEDDING_API_BASE}"
  EMB_MODEL="${OPEN_VIKING_EMBEDDING_MODEL}"
  EMB_DIM="${OPEN_VIKING_EMBEDDING_DIMENSION}"
  VLM_API_KEY="${OPEN_VIKING_VLM_API_KEY}"
  VLM_API_BASE="${OPEN_VIKING_VLM_API_BASE}"
  VLM_MODEL="${OPEN_VIKING_VLM_MODEL}"
else
  echo "using existing config: ${CONFIG_PATH}"
fi

# Generate ov.conf on first run. Server needs server.root_api_key + a working
# embedding.dense provider + a vlm provider, otherwise startup fails inside
# the FastAPI lifespan and the container restart-loops.
if [[ ! -f "${CONFIG_PATH}" ]]; then
  if [[ -z "${OPEN_VIKING_ROOT_API_KEY:-}" ]]; then
    if command -v openssl >/dev/null 2>&1; then
      OPEN_VIKING_ROOT_API_KEY="dev-root-$(openssl rand -hex 12)"
    else
      OPEN_VIKING_ROOT_API_KEY="dev-root-$(python -c 'import secrets; print(secrets.token_hex(12))')"
    fi
  fi
  echo "creating ${CONFIG_PATH} with auto-generated root key + embedding/vlm config"
  cat > "${CONFIG_PATH}" <<EOF
{
  "server": {
    "host": "0.0.0.0",
    "port": 1933,
    "root_api_key": "${OPEN_VIKING_ROOT_API_KEY}"
  },
  "embedding": {
    "dense": {
      "provider": "openai",
      "model": "${EMB_MODEL}",
      "api_key": "${EMB_API_KEY}",
      "api_base": "${EMB_API_BASE}",
      "dimension": ${EMB_DIM},
      "input": "text",
      "encoding_format": "float"
    }
  },
  "vlm": {
    "provider": "openai",
    "model": "${VLM_MODEL}",
    "api_key": "${VLM_API_KEY}",
    "api_base": "${VLM_API_BASE}"
  }
}
EOF
  echo "==> OPEN_VIKING_ROOT_API_KEY=${OPEN_VIKING_ROOT_API_KEY}"
  echo "    export this in your shell to talk to the server."
else
  echo "using existing config: ${CONFIG_PATH}"
fi

echo "Checking existing containers using ${IMAGE} ..."
EXISTING_ID="$(docker ps -a --filter "name=^${CONTAINER}$" --format '{{.ID}}' || true)"
if [[ -n "${EXISTING_ID}" ]]; then
  echo "removing previous container ${CONTAINER} (${EXISTING_ID})"
  docker rm -f "${EXISTING_ID}" >/dev/null
fi

echo "pulling ${IMAGE} ..."
docker pull "${IMAGE}"

echo "starting ${CONTAINER} (API :${API_PORT} / UI :${UI_PORT}) ..."
# MSYS_NO_PATHCONV=1: stop Git Bash from rewriting the container-side path
# of the bind mount (/app/.openviking → D:/Program Files/Git/app/.openviking).
MSYS_NO_PATHCONV=1 docker run -d \
  --name "${CONTAINER}" \
  -p "${API_PORT}:1933" \
  -p "${UI_PORT}:8020" \
  -v "${DATA_DIR}:/app/.openviking" \
  --restart unless-stopped \
  "${IMAGE}"

echo
echo "wait for /health on http://127.0.0.1:${API_PORT} ..."
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
    echo "  ok"
    break
  fi
  sleep 1
done

cat <<EOF

OpenViking running:
  API:  http://127.0.0.1:${API_PORT}
  UI:   http://127.0.0.1:${UI_PORT}
  data: ${DATA_DIR}

Logs:   docker logs -f ${CONTAINER}
Stop:   docker stop ${CONTAINER}
Remove: docker rm -f ${CONTAINER}

For Rath integration tests, export:
  export OPEN_VIKING_URL=http://127.0.0.1:${API_PORT}
  export OPEN_VIKING_ROOT_API_KEY=<the key printed above or from ${CONFIG_PATH}>
EOF
