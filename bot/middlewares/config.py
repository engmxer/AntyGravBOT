"""Configuration injection middleware."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.config.loader import CompanyConfig, EnvConfig


class ConfigMiddleware(BaseMiddleware):
    def __init__(self, company_cfg: CompanyConfig, env_cfg: EnvConfig) -> None:
        self.company_cfg = company_cfg
        self.env_cfg = env_cfg

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["company_cfg"] = self.company_cfg
        data["env_cfg"] = self.env_cfg
        return await handler(event, data)
