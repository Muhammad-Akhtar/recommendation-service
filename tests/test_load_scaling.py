"""Task 24 — demo CPU burn endpoint for HPA load tests."""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client(monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr("app.main.start_producer", _noop)
    monkeypatch.setattr("app.main.stop_producer", _noop)
    monkeypatch.setattr("app.main.init_db", _noop)
    monkeypatch.setattr("app.main.close_db", _noop)

    with TestClient(app) as test_client:
        yield test_client


def test_demo_cpu_burn_clamps_duration(client):
    response = client.get("/demo/cpu-burn", params={"duration_ms": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["duration_ms"] == 5
    assert "service_version" in body


def test_lifespan_tolerates_postgres_init_failure(monkeypatch):
    async def boom():
        raise RuntimeError("postgres down")

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr("app.main.init_db", boom)
    monkeypatch.setattr("app.main.start_producer", _noop)
    monkeypatch.setattr("app.main.stop_producer", _noop)
    monkeypatch.setattr("app.main.close_db", _noop)

    with TestClient(app) as test_client:
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
