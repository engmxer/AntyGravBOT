"""Database session middleware."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


class DbMiddleware(BaseMiddleware):
    def __init__(self, engine: AsyncEngine) -> None:
        self.session_factory = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.session_factory() as session:
            data["session"] = session
            return await handler(event, data)
