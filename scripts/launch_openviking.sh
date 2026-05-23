#!/usr/bin/env bash
# Launch a local OpenViking server for memory-plane integration tests.
# Honors OPEN_VIKING_CONFIG (path to ov.conf; default ~/.openviking/ov.conf).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is not on PATH (install from https://docs.astral.sh/uv/)" >&2
  exit 1
fi

CONFIG_PATH="${OPEN_VIKING_CONFIG:-${HOME}/.openviking/ov.conf}"

echo "syncing optional dependency openviking..."
uv sync --extra openviking

if [[ ! -f "${CONFIG_PATH}" ]]; then
  echo "creating default config at ${CONFIG_PATH}"
  mkdir -p "$(dirname "${CONFIG_PATH}")"
  cat > "${CONFIG_PATH}" <<'EOF'
# OpenViking minimal local config.
# Edit before first run for production deployments.
host = "127.0.0.1"
port = 1933
EOF
fi

echo "using config: ${CONFIG_PATH}"
echo "starting openviking-server (Ctrl+C to stop)..."

# Prefer a packaged entrypoint when present; fall back to module form.
if uv run --extra openviking python -c "import importlib.metadata as m; m.entry_points(group='console_scripts').select(name='openviking-server')" >/dev/null 2>&1; then
  exec uv run --extra openviking openviking-server --config "${CONFIG_PATH}"
else
  exec uv run --extra openviking python -m openviking.server --config "${CONFIG_PATH}"
fi
