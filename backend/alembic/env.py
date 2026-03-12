"""Alembic migration environment configuration for Portfolio-AI.

Portfolio-AI uses raw SQL queries without SQLAlchemy ORM models, so we don't use
autogenerate. Migrations are written manually.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import config which handles ~/.env.local loading via dotenv
# Uses PORTFOLIO_DB_URL env var. Override by setting PORTFOLIO_DB_URL before running.
from app.config import sqlalchemy_database_url
from app.constants import DATABASE_URL as _APP_DB_URL

assert _APP_DB_URL is not None, "PORTFOLIO_DB_URL env var required"

# this is the Alembic Config object
config = context.config

# Use DATABASE_URL from app config (reads PORTFOLIO_DB_URL env var)
config.set_main_option("sqlalchemy.url", sqlalchemy_database_url(_APP_DB_URL))

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No SQLAlchemy models - Portfolio-AI uses raw SQL queries
# All migrations are written manually (no autogenerate)
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This emits SQL to stdout instead of executing against the database.
    Useful for generating SQL scripts for review.
    """
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
    """Run migrations in 'online' mode.

    Connects to the database and executes migrations directly.
    """
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
