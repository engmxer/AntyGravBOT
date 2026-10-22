"""APScheduler setup for automated reminder notifications."""
from __future__ import annotations

import logging
from datetime import timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from bot.config.loader import EnvConfig
from bot.database.models import Client
from bot.database.repo import BookingRepo
from bot.utils.notifications import send_reminder

logger = logging.getLogger(__name__)


def setup_scheduler(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    engine: AsyncEngine,
    env: EnvConfig,
) -> None:
    """Configure recurring scheduler jobs."""
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def send_reminders() -> None:
        """Check for upcoming bookings and send reminder messages."""
        logger.debug("Running reminder job...")
        async with session_factory() as session:
            booking_repo = BookingRepo(session)
            # Window: bookings due within (reminder_hours + 0.5h)
            reminder_delta = timedelta(hours=env.reminder_hours + 0.5)
            bookings = await booking_repo.get_upcoming_for_reminder(reminder_delta)

            for booking in bookings:
                res = await session.execute(
                    select(Client).where(Client.id == booking.client_id)
                )
                client = res.scalar_one_or_none()
                if client:
                    await send_reminder(bot, booking, client)
                    await booking_repo.mark_reminder_sent(booking.id)
                    logger.info(
                        f"Reminder sent for booking #{booking.id} to client {client.telegram_id}"
                    )
            await session.commit()

    scheduler.add_job(
        send_reminders,
        trigger="interval",
        minutes=15,
        id="send_reminders",
        replace_existing=True,
    )
    logger.info("Scheduler configured: reminder check every 15 minutes")
