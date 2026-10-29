"""Podstawowy klient HTTP dla crawlera (faza 2): statyczny HTML + JSON-LD."""
from __future__ import annotations

from typing import Any, cast

import httpx

from ..config import settings


def fetch(url: str, *, timeout: float = 10.0) -> str | None:
    """Pobiera stronę (follow redirects, realistyczny UA). None przy błędzie/403/404."""
    headers = {
        "User-Agent": settings.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    }
    try:
        response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    return response.text


def fetch_json(url: str, *, timeout: float = 10.0) -> Any | None:
    """Pobiera JSON (przyda się w fazie ATS)."""
    try:
        response = httpx.get(url, headers={"User-Agent": settings.user_agent}, timeout=timeout,
                             follow_redirects=True)
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    try:
        return cast(Any, response.json())
    except ValueError:
        return None