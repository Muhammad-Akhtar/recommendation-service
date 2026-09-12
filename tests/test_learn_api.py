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
    assert phase2["status"] == "COMPLETED"
    assert phase2["has_implementation"] is True
    assert "2.1" in phase2["task_ids"]
    phase3 = phases[2]
    assert phase3["number"] == 3
    assert phase3["status"] == "COMPLETED"
    assert phase3["has_implementation"] is True
    assert "3.1" in phase3["task_ids"]
    phase5 = phases[4]
    assert phase5["number"] == 5
    assert phase5["status"] == "COMPLETED"
    assert phase5["has_implementation"] is True
    phase6 = phases[5]
    assert phase6["number"] == 6
    assert phase6["status"] == "COMPLETED"
    assert phase6["has_implementation"] is True
    phase8 = phases[7]
    assert phase8["number"] == 8
    assert phase8["status"] == "COMPLETED"
    assert phase8["has_implementation"] is True
    phase9 = phases[8]
    assert phase9["number"] == 9
    assert phase9["status"] == "IN PROGRESS"
    assert phase9["has_implementation"] is False
    assert "Phase 9" in (body["next_action"] or "")


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


def test_phase_2_markdown_and_tasks(client):
    response = client.get("/api/learn/phases/2")
    assert response.status_code == 200
    body = response.json()
    assert "Data and Feature Engineering" in body["markdown"]
    ids = [t["id"] for t in body["tasks"]]
    assert ids == ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6"]
    assert body["notes_available"] is True
    assert body["has_implementation"] is True


def test_task_2_4_returns_spec_and_implementation(client):
    response = client.get("/api/learn/phases/2/tasks/2.4")
    assert response.status_code == 200
    body = response.json()
    assert "click_count_before" in body["spec"]
    impl = body["implementation"]
    assert impl is not None
    assert impl["path"] == "ml/phase02_features/point_in_time.py"
    assert impl["language"] == "python"
    assert "strictly before" in impl["content"]


def test_phase_2_notes_include_point_in_time_lesson(client):
    response = client.get("/api/learn/phases/2/notes")
    assert response.status_code == 200
    combined = "\n".join(f["content"] for f in response.json()["files"])
    assert "clicked" in combined.lower()
    assert "label we" in combined.lower()


def test_phase_3_task_returns_sigmoid_implementation(client):
    response = client.get("/api/learn/phases/3/tasks/3.1")
    assert response.status_code == 200
    body = response.json()
    assert "sigmoid" in body["spec"].lower()
    impl = body["implementation"]
    assert impl is not None
    assert impl["path"] == "ml/phase03_classical_ml/sigmoid.py"
    assert "def sigmoid" in impl["content"]


def test_phase_4_task_returns_architecture_note(client):
    response = client.get("/api/learn/phases/4/tasks/4.1")
    assert response.status_code == 200
    body = response.json()
    impl = body["implementation"]
    assert impl["path"] == "ml/phase04_recsys/NOTES_architecture.md"
    assert "popular-fallback" in impl["content"] or "POPULAR_RECOMMENDATIONS" in impl["content"]


def test_phase_5_task_returns_ranking_metrics(client):
    response = client.get("/api/learn/phases/5/tasks/5.3")
    assert response.status_code == 200
    body = response.json()
    assert "ndcg" in body["spec"].lower()
    impl = body["implementation"]
    assert impl["path"] == "ml/phase05_evaluation/ranking_metrics.py"
    assert "def ndcg_at_k" in impl["content"]


def test_phase_6_task_returns_pipeline_note(client):
    response = client.get("/api/learn/phases/6/tasks/6.1")
    assert response.status_code == 200
    body = response.json()
    impl = body["implementation"]
    assert impl["path"] == "ml/phase06_train_serve/NOTES_pipeline.md"
    assert "redis" in impl["content"].lower()


def test_phase_7_task_returns_feature_rules(client):
    response = client.get("/api/learn/phases/7/tasks/7.2")
    assert response.status_code == 200
    body = response.json()
    impl = body["implementation"]
    assert impl["path"] == "ml/phase07_feature_store/feature_rules.py"
    assert "apply_event" in impl["content"]


def test_phase_8_task_returns_experiment_log(client):
    response = client.get("/api/learn/phases/8/tasks/8.1")
    assert response.status_code == 200
    body = response.json()
    impl = body["implementation"]
    assert impl["path"] == "ml/phase08_experiments/EXPERIMENT_LOG.md"
    assert "model_version" in impl["content"]


def test_phase_9_task_has_spec_without_implementation(client):
    response = client.get("/api/learn/phases/9/tasks/9.1")
    assert response.status_code == 200
    body = response.json()
    assert "distinction" in body["spec"].lower() or "version" in body["spec"].lower()
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
