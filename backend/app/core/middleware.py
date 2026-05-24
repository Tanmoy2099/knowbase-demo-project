import time
import structlog
from flask import Flask, request, g

logger = structlog.get_logger()


def register_middleware(app: Flask) -> None:
    @app.before_request
    def start_timer() -> None:
        g.start_time = time.monotonic()

    @app.after_request
    def log_request(response):
        duration_ms = round((time.monotonic() - getattr(g, "start_time", time.monotonic())) * 1000, 2)
        logger.info(
            "http_request",
            method=request.method,
            path=request.path,
            status=response.status_code,
            duration_ms=duration_ms,
            content_length=response.content_length,
        )
        return response
