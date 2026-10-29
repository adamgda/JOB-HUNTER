#!/usr/bin/env bash
# JOB-HUNTER — pierwsza konfiguracja środowiska (idempotentna; można uruchamiać ponownie)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== JOB-HUNTER :: setup =="

if ! command -v python3 >/dev/null 2>&1; then
  echo "✖ Brak python3 — zainstaluj (np. brew install python@3.12)" >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "✖ Brak npm/node — zainstaluj node.js (np. brew install node)" >&2
  exit 1
fi

# --- backend -------------------------------------------------------------
UV=""
if command -v uv >/dev/null 2>&1; then
  UV="$(command -v uv)"
elif [ -x "$HOME/.local/bin/uv" ]; then
  UV="$HOME/.local/bin/uv"
fi

if [ -n "$UV" ]; then
  echo "→ uv: buduję backend/.venv na Pythonie 3.12 (Python 3.9 Apple na macOS 27 pada z SIGSEGV)"
  (
    cd backend
    rm -rf .venv
    "$UV" venv .venv --python 3.12 >/dev/null
    "$UV" pip install -r requirements.txt -p .venv/bin/python --quiet
  )
else
  echo "→ uv nieobecny — stara ścieżka python3."
  echo "  (uwaga: systemowy Python 3.9 Apple bywa niestabilny na macOS 27;"
  echo "   polecam zainstalować uv:  curl -LsSf https://astral.sh/uv/install.sh | sh)"
  if [ ! -x backend/.venv/bin/python ]; then
    echo "→ tworzę środowisko wirtualne backend/.venv"
    python3 -m venv backend/.venv
  fi
  echo "→ pip install (backend/requirements.txt)"
  ./backend/.venv/bin/python -m pip install --quiet --upgrade pip >/dev/null
  ./backend/.venv/bin/python -m pip install --quiet -r backend/requirements.txt
fi

# --- frontend ------------------------------------------------------------
if [ ! -d frontend/node_modules ]; then
  echo "→ npm install (frontend)"
  (cd frontend && npm install --no-fund --no-audit --loglevel=error)
fi

# --- konfiguracja --------------------------------------------------------
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "→ utworzono backend/.env — Google działa bez kluczy (silnik google_free/ddgs)"
fi

mkdir -p logs .run
echo
echo "✔ Setup gotowy. Uruchom aplikację:  ./scripts/start.sh  ·  testy: ./scripts/test.sh"