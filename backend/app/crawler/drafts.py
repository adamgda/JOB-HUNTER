"""Wspólny typ roboczy crawlera: roboczy szkic oferty przed zapisem."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OfferDraft:
    """Szkic oferty wydobyty ze strony kariery (przed upsert'em)."""

    title: str
    url: str
    location: str | None = None
    salary: str | None = None
    text_lang: str | None = None