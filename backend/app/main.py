"""JOB-HUNTER — punkt wejścia FastAPI (uvicorn app.main:app)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import routes_exclusions, routes_offers, routes_search
from .config import settings
from .storage import db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="JOB-HUNTER",
        version="0.1.0",
        description="Wyszukiwarka ofert pracy firm, które nie publikują ofert na jobboardach.",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(routes_search.router)
    application.include_router(routes_offers.router)
    application.include_router(routes_exclusions.router)

    @application.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "db": str(settings.db_path)}

    return application


app = create_app()