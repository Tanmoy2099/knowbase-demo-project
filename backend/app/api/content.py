import os
import structlog
from flask import Blueprint, request, jsonify, current_app
from pydantic import BaseModel, ValidationError, model_validator
from typing import Optional, Literal
from werkzeug.utils import secure_filename

from app.core.n8n_client import N8NClient
import app.services.content_service as content_service

ALLOWED_MIME_TYPES = {"application/pdf"}
MAX_PDF_SIZE = 50 * 1024 * 1024  # 50 MB

logger = structlog.get_logger()

content_bp = Blueprint("content", __name__)


class CreateContentRequest(BaseModel):
    type: Literal["link", "note", "pdf", "youtube"]
    raw_url: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    extra_context: Optional[str] = None
    user_instructions: Optional[str] = None

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
        extra_context=payload.extra_context,
        user_instructions=payload.user_instructions,
    )

    try:
        from flask import current_app
        n8n = N8NClient(
            base_url=current_app.config["N8N_BASE_URL"],
            api_key=current_app.config["N8N_API_KEY"],
        )
        n8n.trigger_ingestion(
            {
                "content_item_id": item.id,
                "type": payload.type,
                "raw_url": payload.raw_url,
                "body": payload.body,
            },
            webhook_secret=current_app.config.get("N8N_WEBHOOK_SECRET", ""),
        )
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


@content_bp.post("/upload")
def upload_pdf():
    """Accept a PDF file upload, extract text, save as content item, enrich with AI."""
    if "file" not in request.files:
        return jsonify({"data": None, "error": {"code": "BAD_REQUEST", "message": "No file part in request"}}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"data": None, "error": {"code": "BAD_REQUEST", "message": "No file selected"}}), 400

    # MIME type validation — check both declared type and magic bytes
    mime = file.content_type or ""
    if mime not in ALLOWED_MIME_TYPES:
        # fallback: check filename extension
        if not file.filename.lower().endswith(".pdf"):
            return jsonify({"data": None, "error": {"code": "UNSUPPORTED_MEDIA_TYPE", "message": "Only PDF files are accepted"}}), 415

    filename = secure_filename(file.filename)
    upload_dir = current_app.config.get("UPLOAD_FOLDER", "/app/uploads")
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, filename)
    file.save(save_path)

    try:
        text = content_service.extract_pdf_text(save_path)
    except Exception as e:
        logger.warning("PDF text extraction failed", filename=filename, error=str(e))
        text = ""

    title = request.form.get("title") or filename.rsplit(".", 1)[0]

    item = content_service.create_content_item(
        type_="pdf",
        title=title,
        body=text,
    )

    # PDF is already extracted — run AI enrichment directly without n8n
    try:
        from app.services.ai_service import enrich_content_item
        enrich_content_item(item.id, text, "pdf")
    except Exception as e:
        logger.warning("PDF AI enrichment failed", item_id=item.id, error=str(e))

    return jsonify({"data": item.to_dict(), "meta": None, "error": None}), 201
