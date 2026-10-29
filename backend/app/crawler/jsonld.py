"""Ekstrakcja JSON-LD `"@type": "JobPosting"` — uniwersalny standard ofert w HTML."""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .drafts import OfferDraft

_UNIT_LABELS = {"MONTH": "mies.", "YEAR": "rok", "HOUR": "godz.", "WEEK": "tydz."}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [value]


def _job_posting_to_draft(item: dict[str, Any], base_url: str) -> OfferDraft | None:
    types = [str(t) for t in _as_list(item.get("@type", []))]
    if "JobPosting" not in types:
        return None
    title = str(item.get("title") or item.get("name") or "").strip()
    url = item.get("url") or item.get("@id") or base_url
    if not title or not url:
        return None

    location = ""
    job_locations = _as_list(item.get("jobLocation"))
    for job_location in job_locations:
        address = job_location.get("address") if isinstance(job_location, dict) else None
        if isinstance(address, dict):
            parts = [
                str(address.get(key))
                for key in ("addressLocality", "addressRegion")
                if address.get(key)
            ]
            if parts:
                location = ", ".join(parts)
                break

    salary = ""
    base_salary = item.get("baseSalary")
    if isinstance(base_salary, dict) and isinstance(base_salary.get("value"), dict):
        value = base_salary["value"]
        span = "-".join(
            str(value.get(key)) for key in ("minValue", "maxValue") if value.get(key) is not None
        )
        if span:
            currency = base_salary.get("currency") or value.get("currency") or ""
            unit = str(value.get("unitText") or "")
            unit_label = _UNIT_LABELS.get(unit, unit)
            salary = f"{span} {currency}".strip()
            if unit_label:
                salary += f" / {unit_label}"

    return OfferDraft(
        title=title[:200],
        url=urljoin(base_url, str(url)),
        location=location or None,
        salary=salary or None,
    )


def extract_job_postings(html: str, base_url: str) -> list[OfferDraft]:
    """Wydobywa JobPosting ze wszystkich znaczników <script type='application/ld+json'>."""
    soup = BeautifulSoup(html, "html.parser")
    drafts: list[OfferDraft] = []
    for tag in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except (ValueError, TypeError):
            continue
        items: list[Any] = []
        if isinstance(data, dict):
            graph = data.get("@graph")
            if isinstance(graph, list):
                items = graph
            else:
                items = [data]
        elif isinstance(data, list):
            items = data
        for item in items:
            if isinstance(item, dict):
                draft = _job_posting_to_draft(item, base_url)
                if draft is not None:
                    drafts.append(draft)
    return drafts