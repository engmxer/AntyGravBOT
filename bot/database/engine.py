"""Database engine initialization."""
from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from bot.database.models import Base

logger = logging.getLogger(__name__)


async def init_db(database_url: str) -> AsyncEngine:
    """Create engine, run migrations, return engine."""
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info(f"Database initialized: {database_url}")
    return engine


def get_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
