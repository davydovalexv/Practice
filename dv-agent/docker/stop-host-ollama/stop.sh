#!/usr/bin/env bash
# Остановить Ollama на хосте (systemd), чтобы освободить порт 11434 для контейнера.
set -euo pipefail

echo "==> Остановка host Ollama (освобождение порта 11434)..."
if command -v nsenter >/dev/null 2>&1; then
  nsenter -t 1 -m -u -i -n systemctl stop ollama 2>/dev/null || true
else
  echo "    nsenter недоступен — пропуск"
fi
echo "==> Готово"
