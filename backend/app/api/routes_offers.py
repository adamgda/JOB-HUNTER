"""Endpointy ofert, firm, eksportu CSV i crawlera stron kariery."""
from __future__ import annotations

import csv
import io
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..crawler import career_page
from ..search.languages import detect_languages_text
from ..search.textlang import detect_text_lang
from ..storage import db

router = APIRouter(prefix="/api", tags=["offers"])


class OfferPatch(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


@router.get("/offers")
def get_offers(
    status: Optional[str] = None,
    q: Optional[str] = None,
    source: Optional[str] = None,
    company: Optional[str] = None,
    language: Optional[str] = None,
    text_lang: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    if status and status not in db.STATUSES:
        raise HTTPException(
            status_code=400, detail=f"Nieznany status; dozwolone: {', '.join(db.STATUSES)}"
        )
    conn = db.get_conn()
    items, total = db.list_offers(
        conn,
        status=status,
        q=q,
        source=source,
        company=company,
        language=language,
        text_lang=text_lang,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total}


@router.patch("/offers/{offer_id}")
def patch_offer(offer_id: int, body: OfferPatch) -> dict[str, Any]:
    conn = db.get_conn()
    if db.get_offer(conn, offer_id) is None:
        raise HTTPException(status_code=404, detail=f"Nie ma oferty o id {offer_id}")
    try:
        updated = db.update_offer(conn, offer_id, status=body.status, notes=body.notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return updated


@router.delete("/offers/{offer_id}")
def delete_offer(offer_id: int) -> dict[str, Any]:
    conn = db.get_conn()
    if not db.delete_offer(conn, offer_id):
        raise HTTPException(status_code=404, detail=f"Nie ma oferty o id {offer_id}")
    return {"deleted": True, "id": offer_id}


@router.get("/companies")
def get_companies() -> dict[str, Any]:
    conn = db.get_conn()
    return {"items": db.list_companies(conn)}


@router.post("/companies/{company_id}/refresh")
def refresh_company(company_id: int) -> dict[str, Any]:
    """Wejdź na stronę kariery firmy i wyciągnij oferty (JSON-LD / linki)."""
    conn = db.get_conn()
    company = db.get_company(conn, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Nie ma firmy o id {company_id}")
    summary = career_page.explore_company(company["domain"])

    candidates_found = 0
    new_offers = 0
    duplicates = 0
    for draft in summary.get("drafts", []):
        if not draft.title or not draft.url:
            continue
        candidates_found += 1
        _, created = db.upsert_offer(
            conn,
            company_id=company_id,
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

    return {
        "company": company,
        "career_url": summary.get("career_url"),
        "pages_visited": summary.get("pages_visited", []),
        "candidates_found": candidates_found,
        "new_offers": new_offers,
        "duplicates": duplicates,
        "errors": summary.get("errors", []),
    }


@router.get("/export.csv")
def export_csv() -> StreamingResponse:
    conn = db.get_conn()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["id", "company_domain", "title", "url", "location", "salary",
         "source", "status", "notes", "first_seen"]
    )
    for offer in db.all_offers_for_export(conn):
        writer.writerow(
            [offer["id"], offer["company_domain"], offer["title"], offer["url"],
             offer["location"], offer["salary"], offer["source"], offer["status"],
             offer["notes"], offer["first_seen"]]
        )
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="jobhunter-offers.csv"'},
    )