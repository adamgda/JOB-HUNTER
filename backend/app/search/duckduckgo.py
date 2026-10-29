"""Wariant C: DuckDuckGo (biblioteka ddgs) — drugie źródło wyników, darmowe."""
from __future__ import annotations

from .errors import MissingEngineConfigError, SearchEngineError
from .results import SearchResult


def search(query: str, *, limit: int = 10, date_restrict: str | None = None) -> list[SearchResult]:
    """Wyszukuje przez DuckDuckGo. date_restrict ignorowane (brak w API ddgs)."""
    try:
        from ddgs import DDGS
    except ImportError as exc:
        raise MissingEngineConfigError(
            "Pakiet 'ddgs' nie jest zainstalowany — uruchom ./scripts/setup.sh (pip install ddgs)."
        ) from exc

    try:
        with DDGS() as ddg:
            rows = ddg.text(query, backend="duckduckgo", max_results=max(int(limit), 1))
    except Exception as exc:  # noqa: BLE001 — biblioteka zewnętrzna, łapiemy wszystko
        raise SearchEngineError(f"DuckDuckGo: {exc}") from exc

    results: list[SearchResult] = []
    for index, row in enumerate(rows or [], start=1):
        url = (row.get("href") or row.get("url") or "").strip()
        if not url:
            continue
        results.append(
            SearchResult(
                source="duckduckgo",
                title=(row.get("title") or "").strip(),
                url=url,
                snippet=(row.get("body") or "").strip(),
                rank=index,
            )
        )
    return results