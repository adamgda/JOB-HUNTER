"""Wykluczone domeny: lista, dodawanie (z natychmiastowym czyszczeniem), usuwanie."""
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..storage import db

router = APIRouter(prefix="/api", tags=["exclusions"])


class ExclusionBody(BaseModel):
    domain: str


def _normalize_domain(raw: str) -> str:
    domain = (raw or "").strip().lower()
    for prefix in ("https://", "http://"):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    if domain.startswith("www."):
        domain = domain[4:]
    if "/" in domain:
        domain = domain.split("/", 1)[0]
    return domain.strip()


@router.get("/exclusions")
def get_exclusions() -> dict[str, Any]:
    conn = db.get_conn()
    return {"items": db.list_exclusions(conn)}


@router.post("/exclusions")
def create_exclusion(body: ExclusionBody) -> dict[str, Any]:
    domain = _normalize_domain(body.domain)
    if not domain or "." not in domain:
        raise HTTPException(status_code=400, detail=f"Domena wygląda na błędną: '{body.domain}'.")
    conn = db.get_conn()
    added = db.add_exclusion(conn, domain)
    # natychmiast czyścimy wpisy tej domeny (indep. czy dopiero dodana)
    pruned = db.prune_excluded_offers(conn, [domain])
    return {"added": added, "domain": domain, "pruned_offers": pruned}


@router.delete("/exclusions/{domain}")
def remove_exclusion(domain: str) -> dict[str, Any]:
    conn = db.get_conn()
    removed = db.delete_exclusion(conn, _normalize_domain(domain))
    if not removed:
        raise HTTPException(status_code=404, detail=f"Na liście wykluczeń nie ma domeny '{domain}'.")
    return {"removed": True, "domain": domain}