import pytest
import os
from app import create_app
from app.core.config import Config
from app.core.db import db as _db


@pytest.fixture(scope="session")
def app():
    """Create app with in-memory SQLite for entire test session."""
    config = Config.for_testing()
    application = create_app(config)
    # Ensure SQLite in-memory is accessible across threads / multiple connections
    application.config.setdefault(
        "SQLALCHEMY_ENGINE_OPTIONS",
        {"connect_args": {"check_same_thread": False}},
    )
    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Roll back all DB changes after each test."""
    with app.app_context():
        yield
        _db.session.rollback()
        # Delete all rows from all tables to isolate tests
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture
def sample_content_item(app):
    from app.models.content_item import ContentItem
    with app.app_context():
        item = ContentItem(type="link", raw_url="https://example.com", title="Test", status="pending")
        _db.session.add(item)
        _db.session.commit()
        _db.session.refresh(item)
        return item
