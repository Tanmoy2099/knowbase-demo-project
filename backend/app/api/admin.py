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
