#!/usr/bin/env bash
# start-relay.sh — launch the local bridge relay on loopback.
# Equivalent of start-relay.ps1 (Windows) for Linux / macOS hosts.
# Usage: ./scripts/start-relay.sh [port]
set -euo pipefail

PORT="${1:-8765}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

# Prefer a venv if present
if [ -d "$ROOT/.venv" ]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

echo "[*] Starting bridge relay on 127.0.0.1:$PORT ..."
exec "$PYTHON" "$ROOT/relay/server.py" --port "$PORT"
