"""Database engine initialization."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from bot.database.models import Base

logger = logging.getLogger(__name__)


async def init_db(database_url: str) -> AsyncEngine:
    """Create engine, create parent directory for SQLite if needed, run migrations, return engine."""
    # Ensure SQLite parent directory exists automatically
    if "sqlite" in database_url and "///" in database_url:
        db_path_str = database_url.split("///", 1)[1]
        # Ignore in-memory sqlite
        if db_path_str and not db_path_str.startswith(":memory:"):
            db_path = Path(db_path_str)
            if not db_path.is_absolute():
                db_path = Path.cwd() / db_path
            db_path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured database directory exists: {db_path.parent}")

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
