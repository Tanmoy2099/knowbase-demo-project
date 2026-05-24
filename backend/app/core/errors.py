import structlog
from flask import Flask, jsonify
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

logger = structlog.get_logger()


def _error_response(code: str, message: str, status: int, details=None):
    body = {"data": None, "error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return jsonify(body), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(400)
    def bad_request(e):
        return _error_response("BAD_REQUEST", str(e.description), 400)

    @app.errorhandler(401)
    def unauthorized(e):
        return _error_response("UNAUTHORIZED", "Unauthorized", 401)

    @app.errorhandler(404)
    def not_found(e):
        return _error_response("NOT_FOUND", "Resource not found", 404)

    @app.errorhandler(405)
    def method_not_allowed(e):
        return _error_response("METHOD_NOT_ALLOWED", "Method not allowed", 405)

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        return _error_response("RATE_LIMIT_EXCEEDED", "Too many requests", 429)

    @app.errorhandler(ValidationError)
    def pydantic_validation_error(e):
        details = [
            {"field": str(err["loc"]), "message": err["msg"]} for err in e.errors()
        ]
        return _error_response("VALIDATION_ERROR", "Request validation failed", 422, details)

    @app.errorhandler(Exception)
    def internal_error(e):
        if isinstance(e, HTTPException):
            return _error_response(
                e.name.upper().replace(" ", "_"), str(e.description), e.code
            )
        logger.exception("Unhandled exception", exc_info=e)
        return _error_response("INTERNAL_ERROR", "An unexpected error occurred", 500)
