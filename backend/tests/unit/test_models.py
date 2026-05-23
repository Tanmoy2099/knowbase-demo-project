import pytest
from app.core.db import db
from app.models.content_item import ContentItem
from app.models.tag import Tag, ContentTag, slugify
from app.models.collection import Collection, CollectionItem
from app.models.summary import Summary


# ─── slugify ────────────────────────────────────────────────────────────────

def test_slugify_basic():
    assert slugify("Machine Learning") == "machine-learning"


def test_slugify_special_chars():
    assert slugify("AI & ML!") == "ai-ml"


def test_slugify_multiple_spaces():
    assert slugify("  hello   world  ") == "hello-world"


def test_slugify_already_slug():
    assert slugify("already-slug") == "already-slug"


def test_slugify_uppercase():
    assert slugify("PYTHON") == "python"


def test_slugify_numbers():
    assert slugify("Python 3.12") == "python-312"


def test_slugify_leading_trailing_hyphens():
    result = slugify("---hello---")
    assert not result.startswith("-")
    assert not result.endswith("-")


# ─── ContentItem ────────────────────────────────────────────────────────────

def test_content_item_to_dict(app):
    with app.app_context():
        item = ContentItem(type="link", raw_url="https://example.com", title="Test", status="pending")
        db.session.add(item)
        db.session.commit()

        d = item.to_dict()
        assert d["type"] == "link"
        assert d["raw_url"] == "https://example.com"
        assert d["status"] == "pending"
        assert "created_at" in d
        assert "updated_at" in d
        # Dates must be ISO strings
        assert isinstance(d["created_at"], str)


def test_content_item_to_dict_includes_title(app):
    with app.app_context():
        item = ContentItem(type="note", body="Body text", title="My Title")
        db.session.add(item)
        db.session.commit()

        d = item.to_dict()
        assert d["title"] == "My Title"
        assert d["body"] == "Body text"


def test_content_item_uuid_generated_automatically(app):
    with app.app_context():
        item = ContentItem(type="note", body="Hello")
        db.session.add(item)
        db.session.commit()
        assert item.id is not None
        assert len(item.id) == 36  # UUID format


def test_content_item_uuid_unique_per_instance(app):
    with app.app_context():
        item1 = ContentItem(type="note", body="A")
        item2 = ContentItem(type="note", body="B")
        db.session.add_all([item1, item2])
        db.session.commit()
        assert item1.id != item2.id


def test_content_item_default_status_is_pending(app):
    with app.app_context():
        item = ContentItem(type="note", body="No status set")
        db.session.add(item)
        db.session.commit()
        assert item.status == "pending"


def test_content_item_timestamps_set_on_create(app):
    with app.app_context():
        item = ContentItem(type="note", body="Timestamps test")
        db.session.add(item)
        db.session.commit()
        assert item.created_at is not None
        assert item.updated_at is not None


def test_content_item_latest_summary_none_when_no_summaries(app):
    with app.app_context():
        item = ContentItem(type="note", body="No summary")
        db.session.add(item)
        db.session.commit()
        assert item.latest_summary is None


# ─── Tag & get_or_create ────────────────────────────────────────────────────

def test_tag_get_or_create_creates_new(app):
    with app.app_context():
        tag = Tag.get_or_create("Python Programming")
        db.session.commit()
        assert tag.name == "Python Programming"
        assert tag.slug == "python-programming"
        assert tag.id is not None


def test_tag_get_or_create_returns_existing(app):
    with app.app_context():
        t1 = Tag.get_or_create("Python")
        db.session.commit()
        t2 = Tag.get_or_create("Python")
        db.session.commit()
        assert t1.id == t2.id


def test_tag_get_or_create_case_insensitive_slug(app):
    with app.app_context():
        t1 = Tag.get_or_create("Machine Learning")
        db.session.commit()
        t2 = Tag.get_or_create("machine learning")
        db.session.commit()
        assert t1.id == t2.id


def test_tag_to_dict(app):
    with app.app_context():
        tag = Tag.get_or_create("Deep Learning")
        db.session.commit()
        d = tag.to_dict()
        assert d["name"] == "Deep Learning"
        assert d["slug"] == "deep-learning"
        assert "id" in d


def test_tag_slug_generated_from_name(app):
    with app.app_context():
        tag = Tag.get_or_create("Natural Language Processing")
        db.session.commit()
        assert tag.slug == "natural-language-processing"


# ─── ContentTag / cascade delete ────────────────────────────────────────────

def test_content_item_cascade_deletes_content_tags(app):
    with app.app_context():
        item = ContentItem(type="note", body="test")
        tag = Tag.get_or_create("test-tag")
        db.session.add(item)
        db.session.flush()

        content_tag = ContentTag(content_item_id=item.id, tag_id=tag.id)
        db.session.add(content_tag)
        db.session.commit()

        item_id = item.id
        tag_id = tag.id

        db.session.delete(item)
        db.session.commit()

        # ContentTag should be deleted, Tag should remain
        remaining_ct = ContentTag.query.filter_by(tag_id=tag_id).all()
        assert len(remaining_ct) == 0
        assert Tag.query.get(tag_id) is not None


def test_multiple_tags_on_content_item(app):
    with app.app_context():
        item = ContentItem(type="link", raw_url="https://example.com")
        db.session.add(item)
        db.session.flush()

        tag1 = Tag.get_or_create("Tag One")
        tag2 = Tag.get_or_create("Tag Two")

        db.session.add(ContentTag(content_item_id=item.id, tag_id=tag1.id))
        db.session.add(ContentTag(content_item_id=item.id, tag_id=tag2.id))
        db.session.commit()

        loaded = ContentItem.query.get(item.id)
        assert len(loaded.content_tags) == 2


# ─── Summary ─────────────────────────────────────────────────────────────────

def test_summary_linked_to_content_item(app):
    with app.app_context():
        item = ContentItem(type="link", raw_url="https://example.com")
        db.session.add(item)
        db.session.flush()

        summary = Summary(
            content_item_id=item.id,
            text="A good summary",
            ai_provider="openai",
            model="gpt-4o-mini",
        )
        db.session.add(summary)
        db.session.commit()

        loaded = ContentItem.query.get(item.id)
        assert len(loaded.summaries) == 1
        assert loaded.latest_summary.text == "A good summary"


def test_summary_to_dict(app):
    with app.app_context():
        item = ContentItem(type="note", body="content")
        db.session.add(item)
        db.session.flush()

        summary = Summary(
            content_item_id=item.id,
            text="Summary text",
            ai_provider="mistral",
            model="mistral-small-latest",
        )
        db.session.add(summary)
        db.session.commit()

        d = summary.to_dict()
        assert d["text"] == "Summary text"
        assert d["ai_provider"] == "mistral"
        assert d["model"] == "mistral-small-latest"
        assert "created_at" in d
        assert isinstance(d["created_at"], str)


def test_latest_summary_returns_most_recent(app):
    """latest_summary returns the summary with the latest created_at."""
    import time
    with app.app_context():
        item = ContentItem(type="note", body="content")
        db.session.add(item)
        db.session.flush()

        s1 = Summary(content_item_id=item.id, text="Old summary", ai_provider="openai", model="gpt-4o-mini")
        db.session.add(s1)
        db.session.flush()

        # Slight sleep to ensure different timestamps
        from datetime import datetime, timezone, timedelta
        from app.models.base import utcnow
        s2 = Summary(content_item_id=item.id, text="New summary", ai_provider="openai", model="gpt-4o-mini")
        # Force s2 to have a later created_at
        s2.created_at = utcnow() + timedelta(seconds=1)
        db.session.add(s2)
        db.session.commit()

        loaded = ContentItem.query.get(item.id)
        assert loaded.latest_summary.text == "New summary"


def test_summary_cascade_deleted_with_content_item(app):
    with app.app_context():
        item = ContentItem(type="note", body="will be deleted")
        db.session.add(item)
        db.session.flush()

        summary = Summary(content_item_id=item.id, text="Summary", ai_provider="openai", model="gpt-4o-mini")
        db.session.add(summary)
        db.session.commit()

        item_id = item.id
        summary_id = summary.id

        db.session.delete(item)
        db.session.commit()

        assert Summary.query.get(summary_id) is None


# ─── Collection & CollectionItem ────────────────────────────────────────────

def test_collection_to_dict(app):
    with app.app_context():
        col = Collection(name="AI Research", slug="ai-research", description="AI topics", ai_suggested=True)
        db.session.add(col)
        db.session.commit()

        d = col.to_dict()
        assert d["name"] == "AI Research"
        assert d["slug"] == "ai-research"
        assert d["description"] == "AI topics"
        assert d["ai_suggested"] is True
        assert "created_at" in d


def test_collection_item_links_content_to_collection(app):
    with app.app_context():
        item = ContentItem(type="link", raw_url="https://ai.example.com")
        col = Collection(name="Research", slug="research", ai_suggested=False)
        db.session.add_all([item, col])
        db.session.flush()

        ci = CollectionItem(collection_id=col.id, content_item_id=item.id)
        db.session.add(ci)
        db.session.commit()

        loaded_item = ContentItem.query.get(item.id)
        assert len(loaded_item.collection_items) == 1
        assert loaded_item.collection_items[0].collection.name == "Research"


def test_content_item_to_detail_dict_includes_relations(app):
    with app.app_context():
        item = ContentItem(type="link", raw_url="https://example.com", title="Test")
        db.session.add(item)
        db.session.flush()

        tag = Tag.get_or_create("Python")
        db.session.add(ContentTag(content_item_id=item.id, tag_id=tag.id))

        summary = Summary(content_item_id=item.id, text="Summary", ai_provider="openai", model="gpt-4o-mini")
        db.session.add(summary)
        db.session.commit()

        from sqlalchemy.orm import joinedload
        from app.models.tag import ContentTag as CT
        loaded = (
            ContentItem.query
            .options(
                joinedload(ContentItem.summaries),
                joinedload(ContentItem.content_tags).joinedload(CT.tag),
                joinedload(ContentItem.collection_items),
            )
            .filter(ContentItem.id == item.id)
            .first()
        )
        d = loaded.to_detail_dict()
        assert "summary" in d
        assert "tags" in d
        assert "collections" in d
        assert d["summary"]["text"] == "Summary"
        assert len(d["tags"]) == 1
        assert d["tags"][0]["name"] == "Python"
