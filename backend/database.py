from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings

# Fly.io uses "postgres://" but SQLAlchemy async requires "postgresql+asyncpg://".
# Pass ssl=False via connect_args — asyncpg ignores sslmode in the URL query string.
_db_url = settings.database_url.replace("postgres://", "postgresql+asyncpg://", 1)
_connect_args = {"ssl": False} if _db_url.startswith("postgresql") else {}

engine = create_async_engine(
    _db_url,
    echo=settings.env == "development",
    connect_args=_connect_args,
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
