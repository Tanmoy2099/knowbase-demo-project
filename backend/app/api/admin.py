import structlog
from flask import Blueprint, jsonify, current_app
from sqlalchemy import text

from app.core.db import db
from app.core.n8n_client import N8NClient
logger = structlog.get_logger()

admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/health")
def health_check():
    db_ok = True
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as e:
        logger.warning("DB health check failed", error=str(e))
        db_ok = False

    n8n_ok = False
    try:
        n8n_client = N8NClient(
            base_url=current_app.config["N8N_BASE_URL"],
            api_key=current_app.config["N8N_API_KEY"],
        )
        n8n_ok = n8n_client.health_check()
    except Exception as e:
        logger.warning("N8N health check failed", error=str(e))

    status = "ok" if db_ok and n8n_ok else "degraded"
    return jsonify({
        "status": status,
        "services": {
            "db": db_ok,
            "n8n": n8n_ok,
        },
    })


@admin_bp.post("/sync-workflows")
def sync_workflows():
    from app.services.sync_service import WorkflowSyncService
    result = WorkflowSyncService().sync()
    return jsonify({"data": result, "error": None})


@admin_bp.post("/rebuild-graph")
def rebuild_graph():
    """Rebuild the topic relationship graph for all enriched content items."""
    from app.services.graph_service import rebuild_graph as _rebuild
    result = _rebuild()
    return jsonify({"data": result, "error": None})


@admin_bp.get("/stuck-items")
def stuck_items():
    """Return pending/fetching items older than 10 minutes for retry."""
    from datetime import datetime, timezone, timedelta
    from app.models.content_item import ContentItem

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    items = ContentItem.query.filter(
        ContentItem.status.in_(["pending", "fetching"]),
        ContentItem.created_at < cutoff,
    ).all()

    return jsonify({
        "data": [
            {
                "id": item.id,
                "type": item.type,
                "raw_url": item.raw_url,
                "body": item.body,
                "status": item.status,
            }
            for item in items
        ],
        "error": None,
    })


@admin_bp.post("/retry-item/<item_id>")
def retry_item(item_id: str):
    """Re-trigger n8n ingestion for a single stuck item."""
    from app.models.content_item import ContentItem
    from app.core.n8n_client import N8NClient
    from app.core.db import db

    item = ContentItem.query.get(item_id)
    if not item:
        return jsonify({"data": None, "error": {"code": "NOT_FOUND", "message": "Item not found"}}), 404

    item.status = "pending"
    db.session.commit()

    try:
        n8n = N8NClient(
            base_url=current_app.config["N8N_BASE_URL"],
            api_key=current_app.config["N8N_API_KEY"],
        )
        n8n.trigger_ingestion(
            {
                "content_item_id": item.id,
                "type": item.type,
                "raw_url": item.raw_url,
                "body": item.body,
            },
            webhook_secret=current_app.config.get("N8N_WEBHOOK_SECRET", ""),
        )
        return jsonify({"data": {"status": "re-triggered"}, "error": None})
    except Exception as e:
        logger.warning("Retry trigger failed", item_id=item_id, error=str(e))
        return jsonify({"data": None, "error": {"code": "TRIGGER_FAILED", "message": str(e)}}), 500
