import pytest
from unittest.mock import patch, MagicMock


# ─── GET /api/admin/health ────────────────────────────────────────────────────

def test_health_check_returns_status(client):
    with patch("app.api.admin.N8NClient") as mock_cls:
        mock_cls.return_value.health_check.return_value = True
        resp = client.get("/api/admin/health")

    assert resp.status_code == 200
    data = resp.get_json()
    assert "status" in data
    assert "services" in data
    assert "db" in data["services"]
    assert "n8n" in data["services"]


def test_health_check_status_ok_when_all_healthy(client):
    with patch("app.api.admin.N8NClient") as mock_cls:
        mock_cls.return_value.health_check.return_value = True
        resp = client.get("/api/admin/health")

    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["services"]["db"] is True
    assert data["services"]["n8n"] is True


def test_health_check_db_always_true_with_test_db(client):
    with patch("app.api.admin.N8NClient") as mock_cls:
        mock_cls.return_value.health_check.return_value = False
        resp = client.get("/api/admin/health")

    data = resp.get_json()
    assert data["services"]["db"] is True
    assert data["services"]["n8n"] is False
    assert data["status"] == "degraded"


def test_health_check_degraded_when_n8n_unreachable(client):
    with patch("app.api.admin.N8NClient") as mock_cls:
        mock_cls.return_value.health_check.side_effect = Exception("connection refused")
        resp = client.get("/api/admin/health")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["services"]["n8n"] is False
    assert data["status"] == "degraded"


def test_health_check_response_shape(client):
    """Response must always have status and services keys."""
    with patch("app.api.admin.N8NClient") as mock_cls:
        mock_cls.return_value.health_check.return_value = True
        resp = client.get("/api/admin/health")

    data = resp.get_json()
    assert set(data.keys()) >= {"status", "services"}
    assert set(data["services"].keys()) >= {"db", "n8n"}


# ─── POST /api/admin/sync-workflows ──────────────────────────────────────────

def test_sync_workflows_endpoint(client):
    with patch("app.api.admin.WorkflowSyncService") as mock_cls:
        mock_cls.return_value.sync.return_value = {
            "created": 0, "updated": 0, "skipped": 2, "failed": 0
        }
        resp = client.post("/api/admin/sync-workflows")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["data"]["skipped"] == 2
    assert data["error"] is None


def test_sync_workflows_returns_all_counters(client):
    with patch("app.api.admin.WorkflowSyncService") as mock_cls:
        mock_cls.return_value.sync.return_value = {
            "created": 1, "updated": 2, "skipped": 3, "failed": 0
        }
        resp = client.post("/api/admin/sync-workflows")

    data = resp.get_json()
    assert data["data"]["created"] == 1
    assert data["data"]["updated"] == 2
    assert data["data"]["skipped"] == 3
    assert data["data"]["failed"] == 0


def test_sync_workflows_calls_sync_service(client):
    with patch("app.api.admin.WorkflowSyncService") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.sync.return_value = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
        mock_cls.return_value = mock_instance

        client.post("/api/admin/sync-workflows")

    mock_instance.sync.assert_called_once()


def test_sync_workflows_with_failures_still_returns_200(client):
    with patch("app.api.admin.WorkflowSyncService") as mock_cls:
        mock_cls.return_value.sync.return_value = {
            "created": 0, "updated": 0, "skipped": 0, "failed": 3
        }
        resp = client.post("/api/admin/sync-workflows")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["data"]["failed"] == 3
    assert data["error"] is None
