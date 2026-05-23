import structlog
from flask import Blueprint, request, jsonify, abort
from pydantic import BaseModel, ValidationError, model_validator
from typing import Optional, Literal

from app.core.rate_limit import limiter
from app.core.n8n_client import N8NClient
import app.services.content_service as content_service

logger = structlog.get_logger()

content_bp = Blueprint("content", __name__)


class CreateContentRequest(BaseModel):
    type: Literal["link", "note", "pdf", "youtube"]
    raw_url: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None

    @model_validator(mode="after")
    def validate_content(self) -> "CreateContentRequest":
        if self.type in ("link", "youtube") and not self.raw_url:
            raise ValueError(f"raw_url is required for type '{self.type}'")
        if self.type == "note" and not self.body:
            raise ValueError("body is required for type 'note'")
        return self


class UpdateContentRequest(BaseModel):
    title: Optional[str] = None
    tag_names: Optional[list[str]] = None
    collection_id: Optional[str] = None


@content_bp.post("/")
@limiter.limit("10 per minute")
def create_content():
    try:
        payload = CreateContentRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as e:
        details = [{"field": str(err["loc"]), "message": err["msg"]} for err in e.errors()]
        return jsonify({"data": None, "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": details}}), 422

    item = content_service.create_content_item(
        type_=payload.type,
        raw_url=payload.raw_url,
        title=payload.title,
        body=payload.body,
    )

    try:
        from flask import current_app
        n8n = N8NClient(
            base_url=current_app.config["N8N_BASE_URL"],
            api_key=current_app.config["N8N_API_KEY"],
        )
        n8n.trigger_ingestion(item.id, payload.type, payload.raw_url, payload.body)
    except Exception as e:
        logger.warning("N8N ingestion trigger failed", item_id=item.id, error=str(e))

    return jsonify({"data": item.to_dict(), "meta": None, "error": None}), 201


@content_bp.get("/")
def list_content():
    tag = request.args.get("tag")
    collection = request.args.get("collection")
    type_ = request.args.get("type")
    q = request.args.get("q")
    status = request.args.get("status")
    try:
        page = int(request.args.get("page", 1))
        per_page = min(int(request.args.get("per_page", 20)), 100)
    except ValueError:
        return jsonify({"data": None, "error": {"code": "BAD_REQUEST", "message": "Invalid pagination parameters"}}), 400

    items, total = content_service.list_content_items(
        tag=tag,
        collection=collection,
        type_=type_,
        q=q,
        status=status,
        page=page,
        per_page=per_page,
    )

    return jsonify({
        "data": [item.to_dict() for item in items],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        },
        "error": None,
    })


@content_bp.get("/<item_id>")
def get_content(item_id: str):
    item = content_service.get_content_item_detail(item_id)
    if not item:
        return jsonify({"data": None, "error": {"code": "NOT_FOUND", "message": "Content item not found"}}), 404
    return jsonify({"data": item.to_detail_dict(), "meta": None, "error": None})


@content_bp.patch("/<item_id>")
def update_content(item_id: str):
    try:
        payload = UpdateContentRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as e:
        details = [{"field": str(err["loc"]), "message": err["msg"]} for err in e.errors()]
        return jsonify({"data": None, "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": details}}), 422

    item = content_service.update_content_item(
        item_id=item_id,
        title=payload.title,
        tag_names=payload.tag_names,
        collection_id=payload.collection_id,
    )
    if not item:
        return jsonify({"data": None, "error": {"code": "NOT_FOUND", "message": "Content item not found"}}), 404

    return jsonify({"data": item.to_dict(), "meta": None, "error": None})


@content_bp.delete("/<item_id>")
def delete_content(item_id: str):
    deleted = content_service.delete_content_item(item_id)
    if not deleted:
        return jsonify({"data": None, "error": {"code": "NOT_FOUND", "message": "Content item not found"}}), 404
    return "", 204
