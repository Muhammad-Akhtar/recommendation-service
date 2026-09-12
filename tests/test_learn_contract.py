"""JSON contract the Learning UI client depends on."""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


@pytest.fixture
def client(monkeypatch):
    get_settings.cache_clear()

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr("app.main.start_producer", _noop)
    monkeypatch.setattr("app.main.stop_producer", _noop)
    monkeypatch.setattr("app.main.init_db", _noop)
    monkeypatch.setattr("app.main.close_db", _noop)

    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_task_payload_shape_for_frontend(client):
    body = client.get("/api/learn/phases/1/tasks/1.1").json()
    for key in ("id", "title", "spec", "done", "implementation"):
        assert key in body
    impl = body["implementation"]
    for key in ("path", "language", "content"):
        assert key in impl
    assert "def predict(" in impl["content"]


def test_phase_2_task_payload_shape_for_frontend(client):
    body = client.get("/api/learn/phases/2/tasks/2.2").json()
    assert body["id"] == "2.2"
    assert body["done"] is True
    impl = body["implementation"]
    assert impl["path"] == "ml/phase02_features/toy_events.py"
    assert "TOY_EVENTS" in impl["content"]
