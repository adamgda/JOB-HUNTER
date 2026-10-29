"""Wchodzenie na www firmy i wyciąganie ofert: JSON-LD + linki do ofert."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from ..search.normalizer import url_hash
from ..search.textlang import detect_text_lang
from .drafts import OfferDraft
from .fetcher import fetch
from .jsonld import extract_job_postings

# Typowe ścieżki karier, gdy strona główna nie linkuje wprost.
CAREER_PATHS = [
    "/kariera", "/careers", "/jobs", "/praca", "/en/careers", "/pl/kariera",
    "/company/careers", "/jobs/careers",
]

CAREER_HREF_RE = re.compile(r"karier|career|jobs|/praca/?|/praca\b|rekrut|vacanc", re.I)
CAREER_TEXT_RE = re.compile(
    r"\b(kariera|kariery|karier|careers?|jobs?|praca|oferty|offers?|rekrutacja|vacanc\w*|dołącz do nas)\b",
    re.I,
)
CAREER_STRONG_RE = re.compile(r"(karier|careers?|jobs|/praca/?|rekrutacja)", re.I)
OFFER_HREF_RE = re.compile(
    r"karier|career|ofert|offer|/jobs?/|/praca/|rekrut|vacanc|stanowisk|position", re.I
)
GENERIC_WORDS = {"więcej", "wiecej", "more", "aplikuj", "apply", "wszystkie", "all",
                 "zobacz", "czytaj", "read", "kliknij", "szczegóły", "szczegoly",
                 "details", "edytuj", "podgląd", "widok"}
_UNWANTED_SUFFIXES = (".pdf", ".jpg", ".jpeg", ".png", ".svg", ".ico", ".webp")


def _host(url: str) -> str:
    return urlsplit(url).netloc.lower()


def find_career_links(html: str, base_url: str) -> list[str]:
    """Linki wewnętrzne prowadzące do zakładki kariery (po href lub tekście)."""
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, str] = {}
    base_host = _host(base_url)
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        absolute = urljoin(base_url + "/", href)
        url = absolute
        if url.lower().endswith(_UNWANTED_SUFFIXES):
            continue
        if _host(url) != base_host:
            continue
        text = anchor.get_text(" ", strip=True)
        matches = CAREER_HREF_RE.search(url) or (
            text and CAREER_TEXT_RE.search(text)
        )
        if matches and url not in found:
            found[url] = text
    return list(found)


def _title_from_url(url: str) -> str:
    """Czytelny tytuł z ostatniego segmentu ścieżki (slug): /kariera/frontend-developer."""
    last = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    if not last or last.isdigit():
        return ""
    return " ".join(part for part in re.split(r"[-_.]+", last) if part).strip()[:200]


def collect_offers(html: str, base_url: str) -> list[OfferDraft]:
    """JSON-LD JobPosting + linki, które wyglądają na indywidualne oferty.
    Każdy szkic dostaje też język tekstu strony (pl/en/…)."""
    drafts: dict[str, OfferDraft] = {}
    for draft in extract_job_postings(html, base_url):
        drafts.setdefault(url_hash(draft.url), draft)
    soup = BeautifulSoup(html, "html.parser")
    page_lang = detect_text_lang(soup.get_text(" ", strip=True))
    base_host = _host(base_url)
    page_url = base_url.rstrip("/")
    for anchor in soup.find_all("a", href=True):
        absolute = urljoin(base_url + "/", anchor["href"])
        url = absolute
        if _host(url) != base_host or url.rsplit("/", 1)[0].rstrip("/") == page_url:
            continue
        if url.lower().endswith(_UNWANTED_SUFFIXES):
            continue
        if not OFFER_HREF_RE.search(url):
            continue
        text = anchor.get_text(" ", strip=True)
        if len(text) < 8 or text.lower() in GENERIC_WORDS:
            text = ""
        title = text or _title_from_url(url)
        if not title:
            continue
        drafts.setdefault(url_hash(url), OfferDraft(title=title[:200], url=url))
    for draft in drafts.values():
        if draft.text_lang is None:
            draft.text_lang = page_lang
    return list(drafts.values())


def explore_company(domain: str, *, max_pages: int = 4) -> dict[str, Any]:
    """Wchodzi na stronę firmy, znajduje zakładkę kariery i zbiera szkice ofert."""
    base = domain if domain.startswith(("http://", "https://")) else f"https://{domain}"
    pages_visited: list[str] = []
    errors: list[str] = []
    home = fetch(base)
    if home is None:
        return {
            "career_url": None,
            "pages_visited": [],
            "drafts": [],
            "errors": [f"Nie udało się pobrać strony głównej: {base}"],
        }
    pages_visited.append(base)

    career_links = find_career_links(home, base)
    # preferuj linki, które wprost wyglądają na stronę kariery (nie artykuł o współpracy)
    career_links.sort(key=lambda url: 0 if CAREER_STRONG_RE.search(url) else 1)
    if career_links:
        candidates = career_links[:max_pages]
    else:
        candidates = [urljoin(base, path) for path in CAREER_PATHS]

    drafts: dict[str, OfferDraft] = {}
    for url in candidates[:max_pages]:
        html = fetch(url)
        if html is None:
            errors.append(f"Nie udało się pobrać: {url}")
            continue
        pages_visited.append(url)
        for draft in collect_offers(html, url):
            drafts.setdefault(url_hash(draft.url), draft)

    return {
        "career_url": candidates[0] if candidates else None,
        "pages_visited": pages_visited,
        "drafts": list(drafts.values()),
        "errors": errors,
    }