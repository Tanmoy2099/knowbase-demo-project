from flask import Blueprint, jsonify

import app.services.tags_service as tags_service

tags_bp = Blueprint("tags", __name__)


@tags_bp.get("/")
def list_tags():
    tags = tags_service.list_tags()
    return jsonify({"data": tags, "meta": None, "error": None})
