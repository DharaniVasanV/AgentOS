"""
migrations/env.py

Purpose
-------
Wires Alembic to use the same DATABASE_URL as the app (via
app.config.settings) instead of a second hardcoded connection string.
Uses a SYNC driver (psycopg2) for the migration run itself even though
the app uses asyncpg at runtime — this is the standard Alembic pattern
and avoids needing async migration machinery for what is a one-shot
DDL script.

IMPORTANT: this project intentionally does NOT use --autogenerate.
Autogenerate compares the full DB against all of Base.metadata, which
would try to "fix" the existing tables (meetings, audit_logs, etc.)
that this service doesn't own. Migrations here are written by hand —
see migrations/versions/0001_create_meeting_agent_tables.py — and only
ever touch the 5 new tables.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config.settings import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
# Alembic's default migration flow uses a sync engine; swap the async
# driver for the sync one for this connection only.
sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
config.set_main_option("sqlalchemy.url", sync_url)

target_metadata = None  # intentionally None -- see docstring above, no autogenerate


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
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
