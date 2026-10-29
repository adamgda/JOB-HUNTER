"""Orkiestracja wyszukiwania: pula zapytań → silniki → normalizacja → SQLite."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as EngineCallTimeout
from typing import Any

from ..config import settings
from ..storage import db
from . import duckduckgo, google_scrape, jobs, meta_ddgs
from .errors import SearchEngineError
from .languages import detect_languages_text
from .normalizer import extract_domain, is_excluded, url_hash
from .textlang import detect_text_lang
from .query_builder import (
    DEFAULT_EXCLUDED_JOBBOARDS,
    build_queries,
    collect_excluded,
)

# Silnik google_scrape to prawdziwe Google (SERP) → obsługuje pełne operatory
# (inurl:/intitle:) jak CSE kiedyś; pozostałe silniki ddgs — tylko formuła "basic".
GOOGLE_ENGINES = ("google_scrape",)

# Twarde limity czasu — chronią UI przed wiecznie krązącym loaderem:
# cała sesja wyszukiwania ≤ SEARCH_DEADLINE_SECONDS, pojedyncze wywołanie ≤ ENGINE_CALL_TIMEOUT.
SEARCH_DEADLINE_SECONDS = 75
ENGINE_CALL_TIMEOUT = 20

_ENGINE_EXECUTOR = ThreadPoolExecutor(max_workers=6, thread_name_prefix="enginecall")


def _engine_call(fn: Any, query: str, *, limit: int, date_restrict: str | None) -> tuple[list[Any], str | None]:
    """Wywołuje silnik z twardym timeoutem; po przekroczeniu zwraca komunikat
    (wątek silnika kończy się przy swoim własnym socktowym timeout)."""
    future = _ENGINE_EXECUTOR.submit(fn, query, limit=max(int(limit), 1), date_restrict=date_restrict)
    try:
        return future.result(timeout=ENGINE_CALL_TIMEOUT), None
    except EngineCallTimeout:
        future.cancel()
        return [], f"Przekroczono {ENGINE_CALL_TIMEOUT} s odpowiedzi silnika — pomijam to zapytanie."
    except SearchEngineError as exc:
        return [], str(exc)
    except Exception as exc:  # noqa: BLE001 — nieoczekiwane błędy bibliotek zewnętrznych
        return [], f"Nieoczekiwany błąd silnika: {exc}"


def build_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Waliduje i normalizuje rządanie wyszukiwania z API."""
    keywords = [k.strip() for k in (payload.get("keywords") or []) if isinstance(k, str) and k.strip()]
    if not keywords:
        raise ValueError("Podaj przynajmniej jedno słowo kluczowe (keywords).")

    engines = [e for e in (payload.get("engines") or ["google_free"]) if e]
    unknown = [engine for engine in engines if engine not in {**ENGINES}]
    if unknown:
        raise ValueError(f"Nieznane silniki: {', '.join(unknown)} (dostępne: {', '.join(ENGINES)})")

    tld = (payload.get("tld") or "").strip() or None
    cities = [str(c).strip() for c in (payload.get("cities") or []) if c and str(c).strip()]
    exclude = [str(d).strip() for d in (payload.get("exclude") or []) if d and str(d).strip()]
    try:
        max_queries = max(int(payload.get("max_queries") or 8), 1)
    except (TypeError, ValueError):
        max_queries = 8
    try:
        num_per_query = max(int(payload.get("num_per_query") or 10), 1)
    except (TypeError, ValueError):
        num_per_query = 10
    try:
        crawl_max_companies = min(max(int(payload.get("crawl_max_companies") or 2), 0), 5)
    except (TypeError, ValueError):
        crawl_max_companies = 2
    auto_crawl = bool(payload.get("auto_crawl", True))
    date_restrict = payload.get("date_restrict") or None

    return {
        "keywords": list(dict.fromkeys(keywords)),
        "tld": tld,
        "cities": cities,
        "exclude": exclude,
        "engines": list(dict.fromkeys(engines)),
        "max_queries": max_queries,
        "num_per_query": num_per_query,
        "date_restrict": date_restrict,
        "auto_crawl": auto_crawl,
        "crawl_max_companies": crawl_max_companies,
    }


ENGINES: dict[str, Any] = {
    "duckduckgo": duckduckgo.search,
    "google_free": meta_ddgs.search_google,
    "bing": meta_ddgs.search_bing,
    "yahoo": meta_ddgs.search_yahoo,
    "brave": meta_ddgs.search_brave,
    "google_scrape": google_scrape.search,
}


def run(req: dict[str, Any], job_id: str | None = None) -> dict[str, Any]:
    conn = db.get_conn()
    exclude_domains = list(dict.fromkeys(db.list_exclusions(conn) + collect_excluded(req["exclude"])))
    pruned_offers = db.prune_excluded_offers(conn, exclude_domains)
    seen_hashes = db.existing_url_hashes(conn)

    totals = {"results_seen": 0, "new_offers": 0, "duplicates": 0, "skipped_excluded": 0}
    queries_executed: list[dict[str, Any]] = []
    deadline = time.monotonic() + SEARCH_DEADLINE_SECONDS
    deadline_hit = False

    for engine in req["engines"]:
        if time.monotonic() > deadline:
            deadline_hit = True
        if deadline_hit:
            queries_executed.append(
                {
                    "engine": engine,
                    "query": None,
                    "skipped": f"Limit czasu wyszukiwania ({SEARCH_DEADLINE_SECONDS} s) — wyniki częściowe.",
                }
            )
            continue
        cap = req["max_queries"]

        queries = build_queries(
            req["keywords"],
            tld=req["tld"],
            cities=req["cities"],
            excluded=req["exclude"],
            max_queries=cap,
            google_style=engine in GOOGLE_ENGINES,
        )
        for query in queries:
            entry: dict[str, Any] = {
                "engine": engine,
                "query": query,
                "results_count": 0,
                "new_offers": 0,
                "duplicates": 0,
                "skipped_excluded": 0,
                "error": None,
            }
            results, call_error = _engine_call(
                ENGINES[engine],
                query,
                limit=req["num_per_query"],
                date_restrict=req["date_restrict"],
            )
            entry["results_count"] = len(results)
            if call_error:
                entry["error"] = call_error

            db.log_query(
                conn,
                query=query,
                engine=engine,
                results_count=entry["results_count"],
                http_status=200 if entry["error"] is None else None,
            )

            for result in results:
                totals["results_seen"] += 1
                domain = extract_domain(result.url)
                if not domain:
                    continue
                if is_excluded(result.url, exclude_domains):
                    entry["skipped_excluded"] += 1
                    totals["skipped_excluded"] += 1
                    continue
                url_h = url_hash(result.url)
                if url_h in seen_hashes:
                    entry["duplicates"] += 1
                    totals["duplicates"] += 1
                    continue
                company_id = db.upsert_company(conn, domain, source_query=query)
                db.upsert_offer(
                    conn,
                    company_id=company_id,
                    url=result.url,
                    title=(result.title or domain)[:200],
                    languages=detect_languages_text(result.title, getattr(result, "snippet", "")),
                    text_lang=detect_text_lang(result.title, getattr(result, "snippet", "")),
                    source=engine,
                    source_query=query,
                )
                seen_hashes.add(url_h)
                entry["new_offers"] += 1
                totals["new_offers"] += 1

            queries_executed.append(entry)
            if job_id:
                jobs.update_progress(
                    job_id,
                    {
                        "done": len(queries_executed),
                        "engine": engine,
                        "query": query,
                        "new_offers": totals["new_offers"],
                        "results_seen": totals["results_seen"],
                        "duplicates": totals["duplicates"],
                    },
                )
            if time.monotonic() < deadline:
                time.sleep(max(0.2, settings.search_delay_seconds))

    # Po wyszukiwaniu: automatyczne wchodzenie na /kariera nowych firm
    # (zamienia "stronę kariery" z wyników w konkretne oferty — największa dźwignia zasięgu).
    crawl_entries: list[dict[str, Any]] = []
    crawl_skipped: str | None = None
    if deadline_hit:
        crawl_skipped = f"Auto-crawl pominięty — przekroczono limit czasu wyszukiwania ({SEARCH_DEADLINE_SECONDS} s)."
    wants_crawl = req.get("auto_crawl", True) and req.get("crawl_max_companies", 2) > 0
    if not crawl_skipped and wants_crawl:
        from ..crawler import career_page  # lokalny import, aby uniknąć cykliczności modułowej

        for company in db.companies_missing_offers(conn, limit=req["crawl_max_companies"]):
            summary = career_page.explore_company(company["domain"])
            new_offers = duplicates = 0
            for draft in summary.get("drafts", []):
                if not draft.title or not draft.url:
                    continue
                _, created = db.upsert_offer(
                    conn,
                    company_id=company["id"],
                    url=draft.url,
                    title=draft.title[:200],
                    location=draft.location,
                    salary=draft.salary,
                    languages=detect_languages_text(draft.title),
                    text_lang=draft.text_lang or "unknown",
                    source="career_page",
                    source_query=None,
                )
                if created:
                    new_offers += 1
                else:
                    duplicates += 1
            totals["new_offers"] += new_offers
            crawl_entries.append(
                {
                    "company": company["domain"],
                    "career_url": summary.get("career_url"),
                    "candidates_found": len(summary.get("drafts", [])),
                    "new_offers": new_offers,
                    "duplicates": duplicates,
                    "errors": summary.get("errors", []),
                }
            )

    return {
        "queries_executed": queries_executed,
        **totals,
        "pruned_offers": pruned_offers,
        "crawl": crawl_entries,
        "crawl_skipped": crawl_skipped,
    }