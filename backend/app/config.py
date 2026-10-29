"""Konfiguracja backendu wczytywana z backend/.env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    db_path: Path
    default_tld: str = "pl"
    user_agent: str = "JOB-HUNTER/0.1 (lokalny, osobisty research ofert pracy)"
    cors_origins: list[str] = field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    search_delay_seconds: float = 0.4


def load_settings() -> Settings:
    load_dotenv(BACKEND_DIR / ".env")
    db_path = Path(os.getenv("DB_PATH") or (BACKEND_DIR / "jobhunter.db"))
    cors_origins = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if origin.strip()
    ]
    try:
        delay = float(os.getenv("SEARCH_DELAY_SECONDS", "0.4"))
    except ValueError:
        delay = 0.4

    return Settings(
        db_path=db_path,
        default_tld=os.getenv("DEFAULT_TLD", "pl").strip() or "pl",
        user_agent=os.getenv("USER_AGENT", "JOB-HUNTER/0.1 (lokalny, osobisty research ofert pracy)"),
        cors_origins=cors_origins,
        search_delay_seconds=delay,
    )


settings = load_settings()