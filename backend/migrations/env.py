import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from environment
pg_host = os.environ.get("POSTGRES_HOST", "postgres")
pg_port = os.environ.get("POSTGRES_PORT", "5432")
pg_db = os.environ.get("POSTGRES_DB", "knowbase")
pg_user = os.environ.get("POSTGRES_USER", "knowbase")
pg_pass = os.environ.get("POSTGRES_PASSWORD", "")
config.set_main_option(
    "sqlalchemy.url",
    f"postgresql+psycopg2://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}",
)

# Import all models so autogenerate detects them
from app.core.db import db
from app.models import *  # noqa: F401, F403

target_metadata = db.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
