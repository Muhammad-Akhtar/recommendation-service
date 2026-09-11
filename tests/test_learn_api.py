"""Learning API integration tests — real docs/ml and ml/ files, no Kafka."""

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


def test_catalog_has_twelve_phases_and_phase1_completed(client):
    response = client.get("/api/learn/catalog")
    assert response.status_code == 200
    body = response.json()
    phases = body["phases"]
    assert len(phases) == 12
    phase1 = phases[0]
    assert phase1["number"] == 1
    assert phase1["status"] == "COMPLETED"
    assert phase1["has_implementation"] is True
    assert "1.1" in phase1["task_ids"]
    phase2 = phases[1]
    assert phase2["number"] == 2
    assert phase2["status"] == "NOT STARTED"
    assert phase2["has_implementation"] is False
    assert body["next_action"]


def test_catalog_contract_keys(client):
    body = client.get("/api/learn/catalog").json()
    assert set(body.keys()) >= {"phases", "next_action"}
    phase = body["phases"][0]
    for key in ("number", "title", "status", "file", "has_implementation", "task_ids"):
        assert key in phase
    assert isinstance(phase["number"], int)
    assert isinstance(phase["task_ids"], list)


def test_phase_1_markdown_and_tasks(client):
    response = client.get("/api/learn/phases/1")
    assert response.status_code == 200
    body = response.json()
    assert "ML Fundamentals" in body["markdown"]
    ids = [t["id"] for t in body["tasks"]]
    assert ids == ["1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7"]
    assert body["notes_available"] is True


def test_task_1_1_returns_spec_and_implementation(client):
    response = client.get("/api/learn/phases/1/tasks/1.1")
    assert response.status_code == 200
    body = response.json()
    assert "y = 2x + 1" in body["spec"]
    impl = body["implementation"]
    assert impl is not None
    assert impl["path"] == "ml/phase01_fundamentals/task_1_1_what_is_a_model.py"
    assert impl["language"] == "python"
    assert "y = w * x + b" in impl["content"] or "w * x + b" in impl["content"]
    assert "def predict" in impl["content"]


def test_phase_1_notes_include_leakage_lesson(client):
    response = client.get("/api/learn/phases/1/notes")
    assert response.status_code == 200
    combined = "\n".join(f["content"] for f in response.json()["files"])
    assert "serving time" in combined.lower() or "unavailable at serving time" in combined


def test_context_includes_model_boundary(client):
    response = client.get("/api/learn/context")
    assert response.status_code == 200
    assert "must NOT" in response.json()["markdown"]


def test_phase_2_task_has_spec_without_implementation(client):
    response = client.get("/api/learn/phases/2/tasks/2.1")
    assert response.status_code == 200
    body = response.json()
    assert "Inspect" in body["spec"] or "schema" in body["spec"].lower()
    assert body["implementation"] is None


def test_unknown_phase_404(client):
    assert client.get("/api/learn/phases/99").status_code == 404


def test_unknown_task_404(client):
    assert client.get("/api/learn/phases/1/tasks/9.9").status_code == 404


def test_file_path_traversal_404(client):
    response = client.get("/api/learn/file", params={"path": "../requirements.txt"})
    assert response.status_code == 404


def test_file_outside_allowlist_404(client):
    response = client.get("/api/learn/file", params={"path": "app/main.py"})
    assert response.status_code == 404


def test_cors_allows_learning_ui_origin(client):
    response = client.get(
        "/api/learn/catalog",
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
