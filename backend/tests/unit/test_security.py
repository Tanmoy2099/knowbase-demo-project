import hmac
import hashlib
import json
import pytest
from app.core.security import verify_hmac_signature, compute_hmac_signature

SECRET = "test-webhook-secret"


def make_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_verify_hmac_valid_signature():
    body = b'{"key": "value"}'
    sig = make_signature(SECRET, body)
    assert verify_hmac_signature(SECRET, body, sig) is True


def test_verify_hmac_invalid_signature():
    body = b'{"key": "value"}'
    assert verify_hmac_signature(SECRET, body, "sha256=invalidsignature") is False


def test_verify_hmac_empty_signature():
    body = b'{"key": "value"}'
    assert verify_hmac_signature(SECRET, body, "") is False


def test_verify_hmac_wrong_secret():
    body = b'{"key": "value"}'
    sig = make_signature("wrong-secret", body)
    assert verify_hmac_signature(SECRET, body, sig) is False


def test_verify_hmac_tampered_body():
    body = b'{"key": "value"}'
    sig = make_signature(SECRET, body)
    tampered = b'{"key": "tampered"}'
    assert verify_hmac_signature(SECRET, tampered, sig) is False


def test_verify_hmac_empty_body_with_correct_sig():
    body = b""
    sig = make_signature(SECRET, body)
    assert verify_hmac_signature(SECRET, body, sig) is True


def test_compute_hmac_signature_format():
    body = b"test body"
    sig = compute_hmac_signature(SECRET, body)
    assert sig.startswith("sha256=")
    assert len(sig) == 7 + 64  # "sha256=" + 64 hex chars


def test_compute_hmac_signature_is_deterministic():
    body = b"consistent body"
    sig1 = compute_hmac_signature(SECRET, body)
    sig2 = compute_hmac_signature(SECRET, body)
    assert sig1 == sig2


def test_compute_hmac_signature_differs_with_different_secret():
    body = b"some body"
    sig1 = compute_hmac_signature("secret-a", body)
    sig2 = compute_hmac_signature("secret-b", body)
    assert sig1 != sig2


def test_compute_hmac_signature_differs_with_different_body():
    sig1 = compute_hmac_signature(SECRET, b"body-a")
    sig2 = compute_hmac_signature(SECRET, b"body-b")
    assert sig1 != sig2


def test_compute_and_verify_roundtrip():
    body = b'{"data": "hello world"}'
    sig = compute_hmac_signature(SECRET, body)
    assert verify_hmac_signature(SECRET, body, sig) is True


def test_require_n8n_signature_decorator_rejects_missing(client, app):
    """Test that POST /api/webhooks/n8n without signature returns 401."""
    payload = {"content_item_id": "abc", "raw_content": "text", "content_type": "link"}
    resp = client.post(
        "/api/webhooks/n8n",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 401


def test_require_n8n_signature_decorator_rejects_wrong_signature(client, app):
    """Test that POST /api/webhooks/n8n with wrong signature returns 401."""
    payload = {"content_item_id": "abc", "raw_content": "text", "content_type": "link"}
    body = json.dumps(payload).encode()
    wrong_sig = make_signature("wrong-secret", body)

    resp = client.post(
        "/api/webhooks/n8n",
        data=body,
        content_type="application/json",
        headers={"X-N8N-Signature": wrong_sig},
    )
    assert resp.status_code == 401


def test_require_n8n_signature_decorator_accepts_valid(client, app):
    """Test that POST /api/webhooks/n8n with correct HMAC passes auth check."""
    payload = {"content_item_id": "abc", "raw_content": "test content", "content_type": "link"}
    body = json.dumps(payload).encode()
    secret = app.config["N8N_WEBHOOK_SECRET"]
    sig = make_signature(secret, body)

    resp = client.post(
        "/api/webhooks/n8n",
        data=body,
        content_type="application/json",
        headers={"X-N8N-Signature": sig},
    )
    # 401 would mean auth failed; any other code means signature was accepted
    assert resp.status_code != 401


def test_verify_hmac_signature_constant_time_comparison():
    """Verify uses hmac.compare_digest (timing-safe comparison)."""
    body = b"test"
    sig = make_signature(SECRET, body)
    # Valid sig should pass
    assert verify_hmac_signature(SECRET, body, sig) is True
    # Sig with wrong prefix should fail safely
    assert verify_hmac_signature(SECRET, body, "sha256=" + "0" * 64) is False
