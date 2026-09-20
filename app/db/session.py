"""Async SQLAlchemy engine and request-scoped database session dependency."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

# These conservative defaults are per API worker, so production worker count must be considered.
engine = create_async_engine(
    settings.async_database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=5,
    pool_timeout=30,
)
session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Give one isolated session to a request and always close it when the request ends."""
    async with session_factory() as session:
        yield session


async def close_database() -> None:
    """Close pooled connections during graceful application shutdown."""
    await engine.dispose()
