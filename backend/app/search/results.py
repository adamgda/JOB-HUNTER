"""Typy wyników wyszukiwania."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchResult:
    """Pojedynczy wynik z silnika wyszukiwania."""

    source: str
    title: str
    url: str
    snippet: str = ""
    rank: int = 0