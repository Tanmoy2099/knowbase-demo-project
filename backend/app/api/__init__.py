from flask import Flask

from .content import content_bp
from .collections import collections_bp
from .tags import tags_bp
from .webhooks import webhooks_bp
from .admin import admin_bp


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(content_bp, url_prefix="/api/content")
    app.register_blueprint(collections_bp, url_prefix="/api/collections")
    app.register_blueprint(tags_bp, url_prefix="/api/tags")
    app.register_blueprint(webhooks_bp, url_prefix="/api/webhooks")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
