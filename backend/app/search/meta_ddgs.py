"""Wspólny silnik na bibliotece ddgs z wyborem backendu: bing / yahoo / brave.

Darmowe źródła równoległe do DuckDuckGo — indeksują inaczej, więc dają
czesto inne firmy w wynikach. Kapryśność danego backendu nie wywala
wyszukiwania: błędy trafiają do podsumowania, a nie wywalają całej sesji.
"""
from __future__ import annotations

from typing import Any

from .errors import MissingEngineConfigError, SearchEngineError
from .results import SearchResult


def _search(query: str, *, limit: int, backend: str, source_label: str, date_restrict=None) -> list[SearchResult]:
    try:
        from ddgs import DDGS
    except ImportError as exc:
        raise MissingEngineConfigError(
            "Pakiet 'ddgs' nie jest zainstalowany — uruchom ./scripts/setup.sh (pip install ddgs)."
        ) from exc

    try:
        kwargs: dict[str, Any] = {"backend": backend, "max_results": max(int(limit), 1)}
        if date_restrict:
            # d7/tydzień → 'w'; m1/miesiąc → 'm' (parametr timelimit ddgs)
            kwargs["timelimit"] = "w" if date_restrict.startswith("d") else "m"
        with DDGS() as ddg:
            rows: list[dict[str, Any]] = ddg.text(query, **kwargs)
    except Exception as exc:  # noqa: BLE001 — biblioteka zewnętrzna, łapiemy wszystko
        raise SearchEngineError(f"{source_label}: {exc}") from exc

    results: list[SearchResult] = []
    for index, row in enumerate(rows or [], start=1):
        url = (row.get("href") or row.get("url") or "").strip()
        if not url:
            continue
        results.append(
            SearchResult(
                source=source_label,
                title=(row.get("title") or "").strip(),
                url=url,
                snippet=(row.get("body") or "").strip(),
                rank=index,
            )
        )
    return results


def search_bing(query: str, *, limit: int = 10, date_restrict=None) -> list[SearchResult]:
    return _search(query, limit=limit, backend="bing", source_label="bing", date_restrict=date_restrict)


def search_yahoo(query: str, *, limit: int = 10, date_restrict=None) -> list[SearchResult]:
    return _search(query, limit=limit, backend="yahoo", source_label="yahoo", date_restrict=date_restrict)


def search_brave(query: str, *, limit: int = 10, date_restrict=None) -> list[SearchResult]:
    return _search(query, limit=limit, backend="brave", source_label="brave", date_restrict=date_restrict)


def search_google(query: str, *, limit: int = 10, date_restrict=None) -> list[SearchResult]:
    """Google przez darmowy backend ddgs — bez kluczy, bez projektów Cloud,
    bez limitu 100/dzień (Google wycofało 'Search the entire web' w PSE dla nowych
    wyszukiwarek, więc CSE nie zastąpi tej ścieżki)."""
    return _search(query, limit=limit, backend="google", source_label="google_free", date_restrict=date_restrict)