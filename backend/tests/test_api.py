import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.storage import db


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_offers_empty(client):
    resp = client.get("/api/offers")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0}


def test_search_requires_keywords(client):
    resp = client.post("/api/search", json={"keywords": []})
    assert resp.status_code == 422


def test_search_unknown_engine(client):
    resp = client.post("/api/search", json={"keywords": ["React"], "engines": ["nope"]})
    assert resp.status_code == 400


def test_offer_lifecycle(client):
    conn = db.get_conn()
    company_id = db.upsert_company(conn, "firma.pl")
    offer_id, created = db.upsert_offer(
        conn,
        company_id=company_id,
        url="https://firma.pl/kariera/oferta-backend",
        title="Backend Developer",
        source="test",
        source_query="q",
    )
    assert created is True

    # ten sam URL po normalizacji (www + utm) = duplikat, nie nowa oferta
    _, created_again = db.upsert_offer(
        conn,
        company_id=company_id,
        url="https://www.firma.pl/kariera/oferta-backend?utm_source=x",
        title="duplikat",
    )
    assert created_again is False

    resp = client.get("/api/offers", params={"q": "Backend"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["company_domain"] == "firma.pl"
    assert items[0]["title"] == "Backend Developer"

    resp = client.patch(f"/api/offers/{offer_id}", json={"status": "aplikowano", "notes": "wysłano CV"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "aplikowano"

    resp = client.patch(f"/api/offers/{offer_id}", json={"status": "złe"})
    assert resp.status_code == 400

    resp = client.get("/api/offers", params={"status": "aplikowano", "company": "firma.pl"})
    assert resp.json()["total"] == 1

    csv_resp = client.get("/api/export.csv")
    assert csv_resp.status_code == 200
    assert "Backend Developer" in csv_resp.text


def test_companies_and_queries_log(client):
    conn = db.get_conn()
    company_id = db.upsert_company(conn, "inna.pl", source_query="q1")
    db.upsert_offer(conn, company_id=company_id, url="https://inna.pl/kariera/a", source="test")
    db.log_query(conn, query="q1", engine="test", results_count=1)

    resp = client.get("/api/companies")
    items = resp.json()["items"]
    assert items[0]["domain"] == "inna.pl"
    assert items[0]["offers_count"] == 1 and items[0]["new_count"] == 1

    resp = client.get("/api/queries")
    assert resp.json()["items"][0]["query"] == "q1"