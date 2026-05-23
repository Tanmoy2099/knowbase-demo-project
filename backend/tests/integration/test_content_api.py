import json
import pytest
from unittest.mock import patch, MagicMock


# ─── POST /api/content ────────────────────────────────────────────────────────

def test_create_content_item_link(client, app):
    with patch("app.api.content.N8NClient") as mock_n8n_cls:
        mock_n8n_cls.return_value.trigger_ingestion.return_value = None

        payload = {"type": "link", "raw_url": "https://example.com", "title": "Example"}
        resp = client.post(
            "/api/content/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    assert resp.status_code == 201
    data = resp.get_json()
    assert data["error"] is None
    assert data["data"]["type"] == "link"
    assert data["data"]["raw_url"] == "https://example.com"
    assert data["data"]["status"] == "pending"
    assert "id" in data["data"]


def test_create_content_item_returns_iso_timestamps(client):
    with patch("app.api.content.N8NClient"):
        payload = {"type": "link", "raw_url": "https://timestamps.example.com"}
        resp = client.post(
            "/api/content/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    assert resp.status_code == 201
    data = resp.get_json()
    assert isinstance(data["data"]["created_at"], str)
    assert isinstance(data["data"]["updated_at"], str)


def test_create_content_requires_url_for_link(client):
    payload = {"type": "link"}  # missing raw_url
    resp = client.post(
        "/api/content/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 422
    data = resp.get_json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_create_content_requires_body_for_note(client):
    payload = {"type": "note"}  # missing body
    resp = client.post(
        "/api/content/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 422
    data = resp.get_json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_create_content_rejects_invalid_type(client):
    payload = {"type": "invalid_type", "raw_url": "https://x.com"}
    resp = client.post(
        "/api/content/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 422


def test_create_note_with_body(client):
    with patch("app.api.content.N8NClient"):
        payload = {"type": "note", "body": "My note content", "title": "My Note"}
        resp = client.post(
            "/api/content/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    assert resp.status_code == 201
    data = resp.get_json()
    assert data["data"]["type"] == "note"
    assert data["data"]["title"] == "My Note"


def test_create_youtube_requires_url(client):
    payload = {"type": "youtube"}  # missing raw_url
    resp = client.post(
        "/api/content/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 422


def test_create_content_n8n_failure_does_not_break_creation(client):
    """Even if n8n trigger fails, the content item is still created."""
    with patch("app.api.content.N8NClient") as mock_n8n_cls:
        mock_n8n_cls.return_value.trigger_ingestion.side_effect = Exception("n8n down")

        payload = {"type": "note", "body": "Content created despite n8n failure"}
        resp = client.post(
            "/api/content/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    assert resp.status_code == 201
    data = resp.get_json()
    assert data["data"]["type"] == "note"


# ─── GET /api/content ─────────────────────────────────────────────────────────

def test_list_content_empty(client):
    resp = client.get("/api/content/")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["error"] is None
    assert data["data"] == []


def test_list_content_returns_created_items(client, app):
    with app.app_context():
        from app.models.content_item import ContentItem
        from app.core.db import db
        item = ContentItem(type="note", body="test", title="Test Item")
        db.session.add(item)
        db.session.commit()

    resp = client.get("/api/content/")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) >= 1


def test_list_content_includes_pagination_meta(client):
    resp = client.get("/api/content/")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "meta" in data
    assert "total" in data["meta"]
    assert "page" in data["meta"]
    assert "per_page" in data["meta"]


def test_list_content_filters_by_type(client, app):
    with app.app_context():
        from app.models.content_item import ContentItem
        from app.core.db import db
        db.session.add(ContentItem(type="note", body="a note"))
        db.session.add(ContentItem(type="link", raw_url="https://example.com"))
        db.session.commit()

    resp = client.get("/api/content/?type=note")
    data = resp.get_json()
    assert all(item["type"] == "note" for item in data["data"])


def test_list_content_filters_by_status(client, app):
    with app.app_context():
        from app.models.content_item import ContentItem
        from app.core.db import db
        db.session.add(ContentItem(type="note", body="pending note", status="pending"))
        db.session.add(ContentItem(type="note", body="enriched note", status="enriched"))
        db.session.commit()

    resp = client.get("/api/content/?status=enriched")
    data = resp.get_json()
    assert all(item["status"] == "enriched" for item in data["data"])


# ─── GET /api/content/<id> ────────────────────────────────────────────────────

def test_get_content_item_not_found(client):
    resp = client.get("/api/content/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["error"]["code"] == "NOT_FOUND"


def test_get_content_item_found(client, app):
    with app.app_context():
        from app.models.content_item import ContentItem
        from app.core.db import db
        item = ContentItem(type="link", raw_url="https://x.com", title="X")
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    resp = client.get(f"/api/content/{item_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["data"]["id"] == item_id
    assert data["data"]["raw_url"] == "https://x.com"


def test_get_content_item_detail_includes_tags_and_summary(client, app):
    with app.app_context():
        from app.models.content_item import ContentItem
        from app.models.tag import Tag, ContentTag
        from app.models.summary import Summary
        from app.core.db import db

        item = ContentItem(type="link", raw_url="https://detail.example.com")
        db.session.add(item)
        db.session.flush()

        tag = Tag.get_or_create("DetailTag")
        db.session.add(ContentTag(content_item_id=item.id, tag_id=tag.id))

        summary = Summary(content_item_id=item.id, text="Detail summary", ai_provider="openai", model="gpt-4o-mini")
        db.session.add(summary)
        db.session.commit()
        item_id = item.id

    resp = client.get(f"/api/content/{item_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "tags" in data["data"]
    assert "summary" in data["data"]
    assert len(data["data"]["tags"]) == 1
    assert data["data"]["summary"]["text"] == "Detail summary"


# ─── DELETE /api/content/<id> ─────────────────────────────────────────────────

def test_delete_content_item(client, app):
    with app.app_context():
        from app.models.content_item import ContentItem
        from app.core.db import db
        item = ContentItem(type="note", body="to delete")
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    resp = client.delete(f"/api/content/{item_id}")
    assert resp.status_code == 204

    resp2 = client.get(f"/api/content/{item_id}")
    assert resp2.status_code == 404


def test_delete_nonexistent_returns_404(client):
    resp = client.delete("/api/content/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["error"]["code"] == "NOT_FOUND"


# ─── PATCH /api/content/<id> ─────────────────────────────────────────────────

def test_patch_content_item_title(client, app):
    with app.app_context():
        from app.models.content_item import ContentItem
        from app.core.db import db
        item = ContentItem(type="note", body="content", title="Old Title")
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    resp = client.patch(
        f"/api/content/{item_id}",
        data=json.dumps({"title": "New Title"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["data"]["title"] == "New Title"


def test_patch_content_item_not_found(client):
    resp = client.patch(
        "/api/content/00000000-0000-0000-0000-000000000000",
        data=json.dumps({"title": "Ghost Title"}),
        content_type="application/json",
    )
    assert resp.status_code == 404


def test_patch_content_item_tags(client, app):
    with app.app_context():
        from app.models.content_item import ContentItem
        from app.core.db import db
        item = ContentItem(type="note", body="tag me")
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    resp = client.patch(
        f"/api/content/{item_id}",
        data=json.dumps({"tag_names": ["Python", "Flask"]}),
        content_type="application/json",
    )
    assert resp.status_code == 200

    # Verify tags were set
    with app.app_context():
        from app.models.content_item import ContentItem
        from app.models.tag import ContentTag
        ct_count = ContentTag.query.filter_by(content_item_id=item_id).count()
        assert ct_count == 2
