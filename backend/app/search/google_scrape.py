"""Wariant B: scrapowanie SERP Google (eksperymentalne; narusza ToS Google —
domyślnie wyłączone, uruchamiać tylko awaryjnie i w małych dawkach)."""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from ..config import settings
from .errors import SearchEngineError
from .normalizer import extract_domain
from .results import SearchResult

SERP_URL = "https://www.google.com/search"
_SKIP_HOSTS = ("google.com", "google.pl", "gstatic.com", "googleusercontent.com")


def search(query: str, *, limit: int = 20, date_restrict: str | None = None) -> list[SearchResult]:
    """Best-effort parsowanie statycznego HTML SERP Google bez przeglądarki."""
    headers = {
        "User-Agent": settings.user_agent,
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    }
    params = {"q": query, "num": max(min(int(limit), 40), 1), "hl": "pl", "gl": "pl"}
    if date_restrict:
        params["tbs"] = f"qdr:{'w' if date_restrict.startswith('d') else 'm'}"
    try:
        response = httpx.get(SERP_URL, params=params, headers=headers, timeout=15.0,
                             follow_redirects=True)
    except httpx.HTTPError as exc:
        raise SearchEngineError(f"Google SERP: błąd sieci: {exc}") from exc
    if response.status_code != 200:
        raise SearchEngineError(
            f"Google SERP HTTP {response.status_code} (możliwa CAPTCHA/blokada; to wariant B — użyj CSE)."
        )

    soup = BeautifulSoup(response.text, "html.parser")
    picked: dict[str, str] = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        candidates: list[str] = []
        if href.startswith("/url?"):
            parsed = parse_qs(urlsplit(href).query)
            if parsed.get("q"):
                candidates.append(parsed["q"][0])
        elif href.startswith(("http://", "https://")):
            candidates.append(href)
        for raw_url in candidates:
            if not raw_url.startswith(("http://", "https://")):
                continue
            host = extract_domain(raw_url)
            if not host or any(host == h or host.endswith("." + h) for h in _SKIP_HOSTS):
                continue
            if raw_url not in picked:
                picked[raw_url] = anchor.get_text(" ", strip=True)

    results: list[SearchResult] = []
    for index, (url, title) in enumerate(picked.items(), start=1):
        if index > limit:
            break
        results.append(
            SearchResult(source="google_scrape", title=title[:200], url=url, rank=index)
        )
    return results