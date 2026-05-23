import hashlib
import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


def make_workflow_json(key: str = "test-workflow") -> dict:
    return {
        "name": "Test Workflow",
        "nodes": [],
        "connections": {},
        "active": True,
        "settings": {},
        "meta": {
            "workflowKey": key,
            "version": "1.0.0",
            "managedBy": "knowbase-sync",
            "hash": "",
        },
    }


def test_compute_hash_is_sha256(app):
    with app.app_context():
        from app.services.sync_service import WorkflowSyncService
        mock_n8n = MagicMock()
        service = WorkflowSyncService(n8n_client=mock_n8n)

        content = '{"key": "value"}'
        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert service._compute_hash(content) == expected


def test_compute_hash_same_content_same_result(app):
    with app.app_context():
        from app.services.sync_service import WorkflowSyncService
        service = WorkflowSyncService(n8n_client=MagicMock())
        content = json.dumps(make_workflow_json())
        assert service._compute_hash(content) == service._compute_hash(content)


def test_compute_hash_different_content_different_result(app):
    with app.app_context():
        from app.services.sync_service import WorkflowSyncService
        service = WorkflowSyncService(n8n_client=MagicMock())
        assert service._compute_hash("abc") != service._compute_hash("def")


def test_compute_hash_empty_string(app):
    with app.app_context():
        from app.services.sync_service import WorkflowSyncService
        service = WorkflowSyncService(n8n_client=MagicMock())
        expected = hashlib.sha256(b"").hexdigest()
        assert service._compute_hash("") == expected


def test_sync_creates_new_workflow(app, tmp_path):
    """When workflow does not exist in DB, sync creates it in n8n and records it."""
    workflow_data = make_workflow_json("new-wf")
    wf_file = tmp_path / "new-wf.json"
    wf_file.write_text(json.dumps(workflow_data))

    with app.app_context():
        from app.services.sync_service import WorkflowSyncService
        import app.services.sync_service as ss

        mock_n8n = MagicMock()
        mock_n8n.create_workflow.return_value = "n8n-id-123"

        original = ss.WORKFLOWS_DIR
        ss.WORKFLOWS_DIR = tmp_path
        try:
            service = WorkflowSyncService(n8n_client=mock_n8n)
            results = service.sync()
        finally:
            ss.WORKFLOWS_DIR = original

        mock_n8n.create_workflow.assert_called_once()
        assert results["created"] == 1
        assert results["skipped"] == 0
        assert results["failed"] == 0


def test_sync_creates_db_record_for_new_workflow(app, tmp_path):
    """After creating workflow in n8n, a WorkflowSync record is persisted."""
    workflow_data = make_workflow_json("db-record-wf")
    wf_file = tmp_path / "db-record-wf.json"
    wf_file.write_text(json.dumps(workflow_data))

    with app.app_context():
        from app.services.sync_service import WorkflowSyncService
        from app.models.workflow_sync import WorkflowSync
        import app.services.sync_service as ss

        mock_n8n = MagicMock()
        mock_n8n.create_workflow.return_value = "n8n-new-id"

        original = ss.WORKFLOWS_DIR
        ss.WORKFLOWS_DIR = tmp_path
        try:
            service = WorkflowSyncService(n8n_client=mock_n8n)
            service.sync()
        finally:
            ss.WORKFLOWS_DIR = original

        record = WorkflowSync.query.filter_by(workflow_name="db-record-wf").first()
        assert record is not None
        assert record.n8n_workflow_id == "n8n-new-id"


def test_sync_skips_unchanged_workflow(app, tmp_path):
    """When hash matches existing record, sync skips n8n API call."""
    workflow_data = make_workflow_json("existing-wf")
    content = json.dumps(workflow_data)
    current_hash = hashlib.sha256(content.encode()).hexdigest()

    wf_file = tmp_path / "existing-wf.json"
    wf_file.write_text(content)

    with app.app_context():
        from app.services.sync_service import WorkflowSyncService
        from app.models.workflow_sync import WorkflowSync
        from app.core.db import db
        import app.services.sync_service as ss

        # Pre-populate DB with matching hash
        db.session.add(WorkflowSync(
            workflow_name="existing-wf",
            n8n_workflow_id="n8n-existing-id",
            hash=current_hash,
        ))
        db.session.commit()

        mock_n8n = MagicMock()

        original = ss.WORKFLOWS_DIR
        ss.WORKFLOWS_DIR = tmp_path
        try:
            service = WorkflowSyncService(n8n_client=mock_n8n)
            results = service.sync()
        finally:
            ss.WORKFLOWS_DIR = original

        mock_n8n.create_workflow.assert_not_called()
        mock_n8n.update_workflow.assert_not_called()
        assert results["skipped"] == 1


def test_sync_updates_changed_workflow(app, tmp_path):
    """When hash differs from existing record, sync updates the n8n workflow."""
    old_content = json.dumps(make_workflow_json("changed-wf"))
    new_workflow_data = {**make_workflow_json("changed-wf"), "name": "Changed Name"}
    new_content = json.dumps(new_workflow_data)
    old_hash = hashlib.sha256(old_content.encode()).hexdigest()

    wf_file = tmp_path / "changed-wf.json"
    wf_file.write_text(new_content)

    with app.app_context():
        from app.services.sync_service import WorkflowSyncService
        from app.models.workflow_sync import WorkflowSync
        from app.core.db import db
        import app.services.sync_service as ss

        db.session.add(WorkflowSync(
            workflow_name="changed-wf",
            n8n_workflow_id="n8n-old-id",
            hash=old_hash,
        ))
        db.session.commit()

        mock_n8n = MagicMock()

        original = ss.WORKFLOWS_DIR
        ss.WORKFLOWS_DIR = tmp_path
        try:
            service = WorkflowSyncService(n8n_client=mock_n8n)
            results = service.sync()
        finally:
            ss.WORKFLOWS_DIR = original

        mock_n8n.update_workflow.assert_called_once_with("n8n-old-id", json.loads(new_content))
        assert results["updated"] == 1
        assert results["created"] == 0


def test_sync_updates_hash_in_db_after_update(app, tmp_path):
    """After updating a workflow, the hash in DB is updated to match new file."""
    old_content = json.dumps(make_workflow_json("hash-update-wf"))
    new_content = json.dumps({**make_workflow_json("hash-update-wf"), "name": "Updated"})
    old_hash = hashlib.sha256(old_content.encode()).hexdigest()
    new_hash = hashlib.sha256(new_content.encode()).hexdigest()

    wf_file = tmp_path / "hash-update-wf.json"
    wf_file.write_text(new_content)

    with app.app_context():
        from app.services.sync_service import WorkflowSyncService
        from app.models.workflow_sync import WorkflowSync
        from app.core.db import db
        import app.services.sync_service as ss

        db.session.add(WorkflowSync(
            workflow_name="hash-update-wf",
            n8n_workflow_id="n8n-abc",
            hash=old_hash,
        ))
        db.session.commit()

        mock_n8n = MagicMock()

        original = ss.WORKFLOWS_DIR
        ss.WORKFLOWS_DIR = tmp_path
        try:
            service = WorkflowSyncService(n8n_client=mock_n8n)
            service.sync()
        finally:
            ss.WORKFLOWS_DIR = original

        record = WorkflowSync.query.filter_by(workflow_name="hash-update-wf").first()
        assert record.hash == new_hash


def test_sync_counts_failed_on_n8n_error(app, tmp_path):
    """When n8n API raises, result counts as failed and does not abort."""
    wf_file = tmp_path / "failing-wf.json"
    wf_file.write_text(json.dumps(make_workflow_json("failing-wf")))

    with app.app_context():
        from app.services.sync_service import WorkflowSyncService
        import app.services.sync_service as ss

        mock_n8n = MagicMock()
        mock_n8n.create_workflow.side_effect = Exception("n8n is down")

        original = ss.WORKFLOWS_DIR
        ss.WORKFLOWS_DIR = tmp_path
        try:
            service = WorkflowSyncService(n8n_client=mock_n8n)
            results = service.sync()
        finally:
            ss.WORKFLOWS_DIR = original

        assert results["failed"] == 1
        assert results["created"] == 0


def test_sync_continues_after_one_failure(app, tmp_path):
    """A failure on one workflow does not stop processing the rest."""
    # Write two workflow files
    (tmp_path / "fail-wf.json").write_text(json.dumps(make_workflow_json("fail-wf")))
    (tmp_path / "ok-wf.json").write_text(json.dumps(make_workflow_json("ok-wf")))

    with app.app_context():
        from app.services.sync_service import WorkflowSyncService
        import app.services.sync_service as ss

        mock_n8n = MagicMock()

        # First call raises, second succeeds
        mock_n8n.create_workflow.side_effect = [
            Exception("n8n error"),  # for fail-wf (alphabetically first)
            "n8n-ok-id",             # for ok-wf
        ]

        original = ss.WORKFLOWS_DIR
        ss.WORKFLOWS_DIR = tmp_path
        try:
            service = WorkflowSyncService(n8n_client=mock_n8n)
            results = service.sync()
        finally:
            ss.WORKFLOWS_DIR = original

        assert results["failed"] == 1
        assert results["created"] == 1
        assert results["failed"] + results["created"] == 2


def test_sync_empty_directory(app, tmp_path):
    """Sync with no workflow files returns all-zero counts."""
    with app.app_context():
        from app.services.sync_service import WorkflowSyncService
        import app.services.sync_service as ss

        mock_n8n = MagicMock()

        original = ss.WORKFLOWS_DIR
        ss.WORKFLOWS_DIR = tmp_path
        try:
            service = WorkflowSyncService(n8n_client=mock_n8n)
            results = service.sync()
        finally:
            ss.WORKFLOWS_DIR = original

        assert results == {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
        mock_n8n.create_workflow.assert_not_called()
        mock_n8n.update_workflow.assert_not_called()
