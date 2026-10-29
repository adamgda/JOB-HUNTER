"""Endpointy wyszukiwania: start w tle (POST), status/podsumowanie (GET), log zapytań."""
from __future__ import annotations

import threading
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..search import jobs, service
from ..storage import db

router = APIRouter(prefix="/api", tags=["search"])


class SearchBody(BaseModel):
    keywords: list[str] = Field(min_length=1, max_length=50)
    tld: Optional[str] = "pl"
    cities: list[str] = []
    exclude: list[str] = []
    engines: list[str] = ["google_free"]
    max_queries: int = Field(default=8, ge=1, le=30)
    num_per_query: int = Field(default=10, ge=1, le=20)
    date_restrict: Optional[str] = None
    auto_crawl: bool = True
    crawl_max_companies: int = Field(default=2, ge=0, le=5)


@router.post("/search")
def start_search(body: SearchBody) -> dict[str, Any]:
    try:
        req = service.build_request(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    search_id, is_fresh = jobs.begin_search()
    if not is_fresh or search_id is None:
        snapshot = jobs.snapshot(search_id or "")
        assert search_id is not None
        return {
            "search_id": search_id,
            "started": False,
            "already_running": True,
            "status": snapshot,
        }

    def worker() -> None:
        try:
            result = service.run(req, job_id=search_id)
            jobs.finish(search_id, result=result, error=None)
        except Exception as exc:  # noqa: BLE001 — wyszukiwanie nie może śledzić procesu
            jobs.finish(search_id, result=None, error=str(exc))
        finally:
            jobs.clear_active(search_id)

    threading.Thread(target=worker, daemon=True).start()
    return {"search_id": search_id, "started": True, "already_running": False}


@router.get("/search/{search_id}")
def search_status(search_id: str) -> dict[str, Any]:
    snapshot = jobs.snapshot(search_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Nie ma wyszukiwania '{search_id}'.")
    return {"search_id": search_id, **snapshot}


@router.get("/queries")
def list_queries(limit: int = 20) -> dict[str, Any]:
    conn = db.get_conn()
    return {"items": db.recent_queries(conn, limit=max(min(limit, 100), 1))}