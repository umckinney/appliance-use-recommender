from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings

# Fly.io uses "postgres://" but SQLAlchemy async requires "postgresql+asyncpg://".
# Internal Fly network (.flycast) doesn't use SSL — disable it to avoid handshake errors.
_db_url = settings.database_url.replace("postgres://", "postgresql+asyncpg://", 1)
if "ssl=" not in _db_url:
    _db_url += ("&" if "?" in _db_url else "?") + "ssl=false"

engine = create_async_engine(_db_url, echo=settings.env == "development")
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
