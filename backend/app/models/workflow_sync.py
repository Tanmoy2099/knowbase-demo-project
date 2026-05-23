from app.core.db import db
from .base import generate_uuid, utcnow


class WorkflowSync(db.Model):
    __tablename__ = "workflow_sync"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    workflow_name = db.Column(db.Text, nullable=False, unique=True)
    n8n_workflow_id = db.Column(db.Text)
    hash = db.Column(db.Text, nullable=False)
    last_synced_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workflow_name": self.workflow_name,
            "n8n_workflow_id": self.n8n_workflow_id,
            "hash": self.hash,
            "last_synced_at": self.last_synced_at.isoformat(),
        }
