#!/usr/bin/env bash
set -euo pipefail

stop_host_ollama() {
  if command -v nsenter >/dev/null 2>&1; then
    nsenter -t 1 -m -u -i -n systemctl stop ollama 2>/dev/null || true
  fi
}

trap stop_host_ollama EXIT INT TERM

stop_host_ollama
exec /bin/ollama "$@"
