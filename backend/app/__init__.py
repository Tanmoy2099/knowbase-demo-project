import dataclasses

import structlog
from flask import Flask

from .core.config import Config
from .core.db import db, migrate
from .core.logging_config import configure_logging
from .core.errors import register_error_handlers
from .core.security import configure_security
from .core.middleware import register_middleware
from .api import register_blueprints

logger = structlog.get_logger()


def create_app(config: Config | None = None) -> Flask:
    app = Flask(__name__)
    # Accept both /api/content and /api/content/ without redirecting.
    # Flask's default strict_slashes=True causes 308 redirects that break CORS preflight.
    app.url_map.strict_slashes = False

    if config is None:
        config = Config.from_env()

    # Copy dataclass fields to Flask config dict
    for field in dataclasses.fields(config):
        app.config[field.name] = getattr(config, field.name)

    configure_logging(app)
    db.init_app(app)
    migrate.init_app(app, db)
    configure_security(app)
    register_middleware(app)
    register_error_handlers(app)
    register_blueprints(app)

    with app.app_context():
        try:
            from .services.sync_service import WorkflowSyncService
            WorkflowSyncService().sync()
        except Exception as e:
            logger.warning("Workflow sync failed on startup", error=str(e))

    return app
