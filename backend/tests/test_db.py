from app.storage import db


def test_prune_excluded(tmp_path):
    """Dodanie domeny do wykluczeń ma czyścić JUŻ ZAPISANE wpisy tej firmy."""
    db.init_db(tmp_path / "t.db")
    conn = db.get_conn()

    good_id = db.upsert_company(conn, "firma.pl")
    db.upsert_offer(conn, company_id=good_id, url="https://firma.pl/kariera/a", source="test")
    spam_id = db.upsert_company(conn, "spam.trulyremotework.com")
    db.upsert_offer(conn, company_id=spam_id, url="https://spam.trulyremotework.com/jobs/x", source="test")
    db.upsert_offer(conn, company_id=spam_id, url="https://spam.trulyremotework.com/jobs/y", source="test")

    deleted = db.prune_excluded_offers(conn, ["trulyremotework.com", "linkedin.com"])
    assert deleted == 2
    assert db.get_company(conn, spam_id) is None      # firma z wykluczenia poszła cała
    assert db.get_company(conn, good_id) is not None  # dobra firma została


def test_delete_offer_cleans_company(tmp_path):
    db.init_db(tmp_path / "t.db")
    conn = db.get_conn()
    company_id = db.upsert_company(conn, "solo.pl")
    offer_id, created = db.upsert_offer(
        conn, company_id=company_id, url="https://solo.pl/kariera/x", source="test"
    )
    assert created is True
    assert db.delete_offer(conn, offer_id) is True
    assert db.get_company(conn, company_id) is None   # jedyna oferta → firma też znika
    assert db.delete_offer(conn, offer_id) is False   # ponowne usunięcie → False


def test_exclusions_seeded_and_prune_api(client):
    """Domyślne wykluczenia zasiane; POST dodaje + natychmiast czyści wpisy."""
    items = client.get("/api/exclusions").json()["items"]
    assert "linkedin.com" in items and len(items) >= 20

    conn = db.get_conn()
    cid = db.upsert_company(conn, "agg.example")
    db.upsert_offer(conn, company_id=cid, url="https://agg.example/jobs/1", source="test")

    resp = client.post("/api/exclusions", json={"domain": "https://WWW.Agg.Example/jobs"})
    assert resp.status_code == 200
    assert resp.json() == {"added": True, "domain": "agg.example", "pruned_offers": 1}

    resp = client.delete("/api/exclusions/agg.example")
    assert resp.status_code == 200 and resp.json()["removed"] is True
    assert client.delete("/api/exclusions/agg.example").status_code == 404