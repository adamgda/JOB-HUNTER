#!/usr/bin/env bash
# JOB-HUNTER — zatrzymuje backend i frontend (PID-y z .run/ + sprzątanie portów)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for name in backend frontend; do
  pidfile=".run/$name.pid"
  if [ -f "$pidfile" ]; then
    pid="$(cat "$pidfile")"
    if kill "$pid" 2>/dev/null; then
      echo "→ zatrzymano $name (PID $pid)"
    else
      echo "→ $name nie był uruchomiony (PID $pid już nieaktywny)"
    fi
    rm -f "$pidfile"
  else
    echo "→ $name nie był uruchomiony"
  fi
done

# sprzątanie osieroconych procesów na portach
for port in 8000 5173; do
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill 2>/dev/null || true
    echo "→ zwolniono port $port"
  fi
done

echo "OK."