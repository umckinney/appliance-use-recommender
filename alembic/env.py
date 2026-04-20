"""Alembic migration environment — async-compatible (asyncpg / aiosqlite)."""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

alembic_cfg = context.config

if alembic_cfg.config_file_name is not None:
    fileConfig(alembic_cfg.config_file_name)

# Import models so SQLAlchemy metadata is populated before autogenerate runs.
import backend.models  # noqa: E402, F401
from backend.database import Base  # noqa: E402

target_metadata = Base.metadata


def _get_async_url() -> str:
    """Return the async database URL from app settings."""
    from backend.config import settings

    url = settings.database_url
    # Normalize bare postgres:// scheme (Fly.io / Heroku style) to asyncpg driver.
    url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


# ---------------------------------------------------------------------------
# Offline mode — emit SQL to stdout without connecting
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    context.configure(
        url=_get_async_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode — connect and apply migrations
# ---------------------------------------------------------------------------


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    cfg = alembic_cfg.get_section(alembic_cfg.config_ini_section, {})
    cfg["sqlalchemy.url"] = _get_async_url()

    connectable = async_engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
