#!/usr/bin/env bash
# start-lightpanda.sh — Linux / macOS native launcher for Lightpanda CDP.
# Equivalent of start-lightpanda.ps1 (Windows/WSL2) for non-Windows hosts.
# Usage: ./scripts/start-lightpanda.sh [port] [cookie-dir]
set -euo pipefail

PORT="${1:-9222}"
COOKIE_DIR="${2:-$HOME/.hermes/lightpanda-a6api}"
BIN="${LIGHTPANDA_BIN:-$HOME/lightpanda}"

if [ ! -x "$BIN" ]; then
  echo "[-] Lightpanda binary not found at: $BIN" >&2
  echo "    Install it first:" >&2
  echo "      curl -fsSL https://pkg.lightpanda.io/install.sh | bash" >&2
  echo "    Or set LIGHTPANDA_BIN=/path/to/lightpanda" >&2
  exit 1
fi

mkdir -p "$COOKIE_DIR"
export LIGHTPANDA_DISABLE_TELEMETRY=true
echo "[*] Starting Lightpanda CDP on 127.0.0.1:$PORT ..."
echo "    Cookie jar: $COOKIE_DIR/cookies.json"
exec "$BIN" serve --host 127.0.0.1 --port "$PORT" \
  --cookie-jar "$COOKIE_DIR/cookies.json" --log-level error
