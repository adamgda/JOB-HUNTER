import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.storage import db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient na świeżej, tymczasowej bazie SQLite."""
    monkeypatch.setattr(config.settings, "db_path", tmp_path / "test.db")
    db.init_db(tmp_path / "test.db")
    return TestClient(app)