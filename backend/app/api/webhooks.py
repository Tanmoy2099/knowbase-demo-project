import structlog
from flask import Blueprint, request, jsonify
from pydantic import BaseModel, ValidationError

from app.core.security import require_n8n_signature
from app.services.ai_service import enrich_content_item

logger = structlog.get_logger()

webhooks_bp = Blueprint("webhooks", __name__)


class N8NWebhookPayload(BaseModel):
    content_item_id: str
    raw_content: str
    content_type: str  # link|note|pdf|youtube


@webhooks_bp.post("/n8n")
@require_n8n_signature
def n8n_webhook():
    try:
        payload = N8NWebhookPayload.model_validate(request.get_json(force=True) or {})
    except ValidationError as e:
        details = [{"field": str(err["loc"]), "message": err["msg"]} for err in e.errors()]
        return jsonify({"data": None, "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": details}}), 422

    try:
        enrich_content_item(
            payload.content_item_id,
            payload.raw_content,
            payload.content_type,
        )
    except Exception as e:
        logger.error("AI enrichment failed in webhook handler", error=str(e), content_item_id=payload.content_item_id)
        return jsonify({"data": None, "error": {"code": "ENRICHMENT_FAILED", "message": "Content enrichment failed"}}), 500

    return jsonify({"data": {"status": "ok"}, "error": None})
