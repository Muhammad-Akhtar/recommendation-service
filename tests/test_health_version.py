"""Task 23 — deploy identity on /health (canary / blue-green)."""

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


def test_health_includes_default_service_version(client, monkeypatch):
    monkeypatch.delenv("SERVICE_VERSION", raising=False)
    get_settings.cache_clear()

    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "v1"


def test_health_service_version_from_env(client, monkeypatch):
    monkeypatch.setenv("SERVICE_VERSION", "v2")
    get_settings.cache_clear()

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "v2"}
