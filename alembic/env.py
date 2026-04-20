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
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    from backend.config import settings

    url = settings.database_url
    # Normalize postgres:// or postgresql:// → postgresql+asyncpg://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Strip target_session_attrs — Fly.io Postgres URLs may include this parameter;
    # asyncpg raises TargetServerAttributeNotMatched if the release-command machine
    # connects to a standby instead of the primary.
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params.pop("target_session_attrs", None)
    new_query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=new_query))


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
    url = _get_async_url()
    cfg["sqlalchemy.url"] = url

    # Mirror database.py: disable SSL on Postgres (Fly.io internal network).
    # Without this asyncpg attempts SSL negotiation which raises
    # TargetServerAttributeNotMatched on the private network.
    connect_args = {"ssl": False} if url.startswith("postgresql") else {}

    connectable = async_engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
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
