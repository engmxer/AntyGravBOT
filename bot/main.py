"""Entry point for the Telegram booking bot."""
import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.loader import load_company_config, load_env_config
from bot.database.engine import init_db
from bot.database.seed import seed_database_from_config
from bot.handlers import register_all_handlers
from bot.middlewares.config import ConfigMiddleware
from bot.middlewares.db import DbMiddleware
from bot.scheduler import setup_scheduler

load_dotenv()


async def main() -> None:
    """Initialize and run the bot."""
    env = load_env_config()
    company_cfg = load_company_config(env.company_config)

    logging.basicConfig(
        level=getattr(logging, env.log_level),
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        stream=sys.stdout,
    )
    logger = logging.getLogger(__name__)
    logger.info(f"Starting bot for company: {company_cfg.name}")

    # Initialize DB (create tables)
    engine = await init_db(env.database_url)

    # Seed initial categories & services from YAML config if DB is empty
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        await seed_database_from_config(session, company_cfg)

    # Bot & Dispatcher
    bot = Bot(
        token=env.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Middlewares
    dp.update.middleware(DbMiddleware(engine))
    dp.update.middleware(ConfigMiddleware(company_cfg=company_cfg, env_cfg=env))

    # Handlers
    register_all_handlers(dp)

    # Scheduler for reminders
    scheduler = AsyncIOScheduler(timezone=env.timezone)
    setup_scheduler(scheduler, bot, engine, env)
    scheduler.start()

    logger.info("Bot started. Polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
