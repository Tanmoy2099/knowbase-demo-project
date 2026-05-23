import hashlib
import json
from pathlib import Path
import structlog
from app.core.db import db
from app.models.workflow_sync import WorkflowSync
from app.core.n8n_client import N8NClient

logger = structlog.get_logger()
WORKFLOWS_DIR = Path(__file__).parent.parent / "workflows"


class WorkflowSyncService:
    def __init__(self, n8n_client: N8NClient | None = None):
        from flask import current_app
        if n8n_client is None:
            n8n_client = N8NClient.from_app_config(current_app.config)
        self.n8n = n8n_client

    def sync(self) -> dict:
        results = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
        workflow_files = sorted(WORKFLOWS_DIR.glob("*.json"))

        logger.info("Starting workflow sync", total=len(workflow_files))

        for path in workflow_files:
            try:
                action = self._sync_one(path)
                results[action] += 1
            except Exception as e:
                logger.warning("Failed to sync workflow", name=path.stem, error=str(e))
                results["failed"] += 1

        logger.info("Workflow sync complete", **results)
        return results

    def _compute_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _sync_one(self, path: Path) -> str:
        content = path.read_text(encoding="utf-8")
        current_hash = self._compute_hash(content)
        workflow_name = path.stem

        existing: WorkflowSync | None = WorkflowSync.query.filter_by(workflow_name=workflow_name).first()

        if existing and existing.hash == current_hash:
            logger.debug("Workflow unchanged, skipping", name=workflow_name)
            return "skipped"

        workflow_data = json.loads(content)

        if existing is None:
            n8n_id = self.n8n.create_workflow(workflow_data)
            record = WorkflowSync(
                workflow_name=workflow_name,
                n8n_workflow_id=n8n_id,
                hash=current_hash,
            )
            db.session.add(record)
            db.session.commit()
            logger.info("Workflow created and synced", name=workflow_name, n8n_id=n8n_id)
            return "created"
        else:
            self.n8n.update_workflow(existing.n8n_workflow_id, workflow_data)
            existing.hash = current_hash
            db.session.commit()
            logger.info("Workflow updated and synced", name=workflow_name)
            return "updated"


def run_sync() -> None:
    service = WorkflowSyncService()
    results = service.sync()
    print(f"Sync complete: {results}")
