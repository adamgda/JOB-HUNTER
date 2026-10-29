#!/usr/bin/env bash
# JOB-HUNTER — uruchamia backend (:8000) i frontend (:5173) w tle.
# UWAGA: celowo NIE używamy launchctl/launchd — Python 3.9 (Build Apple CLT)
# uruchomiony przez launchd pada z SIGSEGV (pointer authentication) na macOS 27
# i wytrąca okno awarii macOS. Stabilna ścieżka: nohup + disown.
# Logi: logs/ · PID-y: .run/ · stop: ./scripts/stop.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p logs .run

if [ ! -x backend/.venv/bin/python ] || [ ! -d frontend/node_modules ]; then
  echo "→ Środowisko nie jest skonfigurowane — uruchamiam setup…"
  ./scripts/setup.sh
fi

# ============ backend ============
BACKEND_UP=0
if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
  echo "Backend już działa."
  BACKEND_UP=1
else
  echo "→ start backendu (http://127.0.0.1:8000)…"
  (
    cd backend
    nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 >> ../logs/backend.log 2>&1 &
    echo $! > ../.run/backend.pid
    disown 2>/dev/null || true
  )
  for _ in $(seq 1 24); do
    if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then BACKEND_UP=1; break; fi
    sleep 0.5
  done
fi
if [ "$BACKEND_UP" != "1" ]; then
  echo "✖ Backend nie wystartował — ostatnie linie logu:" >&2
  tail -n 25 logs/backend.log >&2
  ./scripts/stop.sh >/dev/null 2>&1 || true
  exit 1
fi
echo "  ✔ backend gotowy"

# ============ frontend ============
FRONTEND_UP=0
if curl -fsS http://localhost:5173/ >/dev/null 2>&1; then
  echo "Frontend już działa."
  FRONTEND_UP=1
else
  echo "→ start frontendu (http://localhost:5173)…"
  (
    cd frontend
    nohup npm run dev -- --port 5173 >> ../logs/frontend.log 2>&1 &
    echo $! > ../.run/frontend.pid
    disown 2>/dev/null || true
  )
  for _ in $(seq 1 24); do
    if curl -fsS http://localhost:5173/ >/dev/null 2>&1; then FRONTEND_UP=1; break; fi
    sleep 0.5
  done
fi
if [ "$FRONTEND_UP" != "1" ]; then
  echo "✖ Frontend nie wystartował — ostatnie linie logu:" >&2
  tail -n 25 logs/frontend.log >&2
  ./scripts/stop.sh >/dev/null 2>&1 || true
  exit 1
fi
echo "  ✔ frontend gotowy"

echo
echo "✔ JOB-HUNTER działa:"
echo "   UI:  http://localhost:5173"
echo "   API: http://localhost:8000/docs"
echo "   logi: logs/ · PID-y: .run/ · stop: ./scripts/stop.sh"