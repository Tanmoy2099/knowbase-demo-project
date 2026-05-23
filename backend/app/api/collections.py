import structlog
from flask import Blueprint, request, jsonify
from pydantic import BaseModel, ValidationError
from typing import Optional

import app.services.collections_service as collections_service

logger = structlog.get_logger()

collections_bp = Blueprint("collections", __name__)


class CreateCollectionRequest(BaseModel):
    name: str
    description: Optional[str] = None


class UpdateCollectionRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


@collections_bp.get("/")
def list_collections():
    collections = collections_service.list_collections()
    return jsonify({"data": collections, "meta": None, "error": None})


@collections_bp.post("/")
def create_collection():
    try:
        payload = CreateCollectionRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as e:
        details = [{"field": str(err["loc"]), "message": err["msg"]} for err in e.errors()]
        return jsonify({"data": None, "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": details}}), 422

    collection = collections_service.create_collection(
        name=payload.name,
        description=payload.description,
    )
    return jsonify({"data": collection.to_dict(), "meta": None, "error": None}), 201


@collections_bp.patch("/<collection_id>")
def update_collection(collection_id: str):
    try:
        payload = UpdateCollectionRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as e:
        details = [{"field": str(err["loc"]), "message": err["msg"]} for err in e.errors()]
        return jsonify({"data": None, "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": details}}), 422

    collection = collections_service.update_collection(
        collection_id=collection_id,
        name=payload.name,
        description=payload.description,
    )
    if not collection:
        return jsonify({"data": None, "error": {"code": "NOT_FOUND", "message": "Collection not found"}}), 404

    return jsonify({"data": collection.to_dict(), "meta": None, "error": None})


@collections_bp.delete("/<collection_id>")
def delete_collection(collection_id: str):
    deleted = collections_service.delete_collection(collection_id)
    if not deleted:
        return jsonify({"data": None, "error": {"code": "NOT_FOUND", "message": "Collection not found"}}), 404
    return "", 204
