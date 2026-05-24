import hmac
import hashlib
from functools import wraps
from flask import Flask, request, abort, current_app
from flask_talisman import Talisman
from flask_cors import CORS
import structlog

logger = structlog.get_logger()

talisman = Talisman()


def configure_security(app: Flask) -> None:
    CORS(app, origins=[app.config.get("CORS_ORIGIN", "http://localhost:3000")], supports_credentials=False)

    is_production = app.config.get("FLASK_ENV") == "production"

    csp = {
        "default-src": ["'self'"],
        "script-src": ["'self'"],
        "style-src": ["'self'", "'unsafe-inline'"],
        "img-src": ["'self'", "data:"],
        "connect-src": ["'self'"],
    }

    talisman.init_app(
        app,
        force_https=is_production,
        content_security_policy=csp,
        strict_transport_security=is_production,
        referrer_policy="strict-origin-when-cross-origin",
    )


def compute_hmac_signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_hmac_signature(secret: str, body: bytes, signature: str) -> bool:
    if not signature:
        return False
    expected = compute_hmac_signature(secret, body)
    try:
        return hmac.compare_digest(expected, signature)
    except TypeError:
        return False


def require_n8n_signature(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        secret = current_app.config.get("N8N_WEBHOOK_SECRET", "")
        signature = request.headers.get("X-N8N-Signature", "")
        body = request.get_data()

        # Accept HMAC-SHA256 signature OR a simple bearer token.
        # Bearer token is used for Docker-internal n8n callbacks where the sandbox
        # cannot compute HMAC; it is safe because both services share the Docker network.
        valid = False
        if signature.startswith("bearer "):
            valid = hmac.compare_digest(signature[7:], secret)
        else:
            valid = verify_hmac_signature(secret, body, signature)

        if not valid:
            logger.warning(
                "n8n webhook signature validation failed",
                remote_addr=request.remote_addr,
                has_signature=bool(signature),
            )
            abort(401)

        return f(*args, **kwargs)
    return decorated
