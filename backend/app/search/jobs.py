"""Rejestr wyszukiwań wykonywanych w tle — status, postęp, ograniczenie do 1 aktywnego."""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}
_ACTIVE: str | None = None
_MAX_KEPT_JOBS = 20


def begin_search() -> tuple[str | None, bool]:
    """Rozpoczyna (atomowo) wyszukiwanie.

    Zwraca (search_id, is_fresh):
      fresh=True  → utworzono nowe wyszukiwanie, trzeba uruchomić wątek roboczy,
      fresh=False → _ACTIVE == None (zabrakło miejsca?); lub istnieje aktywna sesja → ID.
    """
    global _ACTIVE
    with _LOCK:
        if _ACTIVE is not None:
            job = _JOBS.get(_ACTIVE)
            if job is not None and job["status"] == "running":
                return _ACTIVE, False
            _ACTIVE = None  # zakończone — zwolnij
        # przycinanie starych wpisów (zostaw ostatnie 20)
        job_ids = list(_JOBS.keys())
        if len(job_ids) > _MAX_KEPT_JOBS:
            for old_id in job_ids[: len(job_ids) - _MAX_KEPT_JOBS]:
                if _JOBS[old_id]["status"] != "running":
                    _JOBS.pop(old_id, None)
        search_id = uuid.uuid4().hex[:8]
        _ACTIVE = search_id
        _JOBS[_ACTIVE] = {
            "status": "running",
            "result": None,
            "error": None,
            "progress": None,
            "started_at": time.time(),
        }
        return search_id, True


def clear_active(search_id: str) -> None:
    global _ACTIVE
    with _LOCK:
        if _ACTIVE == search_id:
            _ACTIVE = None


def finish(search_id: str, *, result: dict[str, Any] | None, error: str | None) -> None:
    with _LOCK:
        job = _JOBS.get(search_id)
        if job is not None:
            job["status"] = "error" if error else "done"
            job["result"] = result
            job["error"] = error
            job["finished_at"] = time.time()


def update_progress(search_id: str, progress: dict[str, Any]) -> None:
    with _LOCK:
        job = _JOBS.get(search_id)
        if job is not None:
            job["progress"] = progress


def snapshot(search_id: str) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(search_id)
        if job is None:
            return None
        snapshot = dict(job)
        snapshot["elapsed"] = round(time.time() - float(job.get("started_at") or time.time()), 1)
        return snapshot