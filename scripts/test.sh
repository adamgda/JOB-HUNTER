#!/usr/bin/env bash
# JOB-HUNTER — testy backendu (pytest)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -x backend/.venv/bin/python ]; then
  echo "→ brak venv — uruchamiam setup…"
  ./scripts/setup.sh
fi

cd backend
.venv/bin/python -m pytest -q