"""Admin and client notification utilities."""
from __future__ import annotations

import logging
from datetime import timedelta

from aiogram import Bot

from bot.config.loader import CompanyConfig
from bot.database.models import Booking, Client

logger = logging.getLogger(__name__)


async def notify_admin_new_booking(
    bot: Bot,
    booking: Booking,
    client: Client,
    company_cfg: CompanyConfig,
) -> None:
    """Send notification to the admin/company chat about a new booking."""
    from bot.config.loader import load_env_config
    try:
        env = load_env_config()
        if not env.notify_chat_id:
            return
        ends_at = booking.starts_at + timedelta(minutes=booking.duration_minutes)
        text = (
            f"🔔 <b>Новая запись!</b>\n\n"
            f"💅 Услуга: <b>{booking.service_name}</b>\n"
            f"👤 Клиент: <b>{client.full_name or client.first_name or 'Не указан'}</b>\n"
            f"📞 Телефон: <b>{client.phone or 'Не указан'}</b>\n"
            f"🆔 Telegram: @{client.username or str(client.telegram_id)}\n"
            f"📅 Дата: <b>{booking.starts_at.strftime('%d.%m.%Y')}</b>\n"
            f"🕐 Время: <b>{booking.starts_at.strftime('%H:%M')} – {ends_at.strftime('%H:%M')}</b>\n"
            f"👨‍💼 Мастер: <b>{booking.master_name or 'Не указан'}</b>\n"
            f"💰 Стоимость: <b>{booking.price} ₽</b>\n"
            f"🔑 ID записи: <b>#{booking.id}</b>"
        )
        await bot.send_message(env.notify_chat_id, text)
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")


async def send_reminder(bot: Bot, booking: Booking, client: Client) -> None:
    """Send reminder message to the client before their appointment."""
    try:
        ends_at = booking.starts_at + timedelta(minutes=booking.duration_minutes)
        text = (
            f"⏰ <b>Напоминание о записи!</b>\n\n"
            f"Скоро у вас запись:\n\n"
            f"💅 Услуга: <b>{booking.service_name}</b>\n"
            f"📅 Дата: <b>{booking.starts_at.strftime('%d.%m.%Y')}</b>\n"
            f"🕐 Время: <b>{booking.starts_at.strftime('%H:%M')} – {ends_at.strftime('%H:%M')}</b>\n"
            f"👨‍💼 Мастер: <b>{booking.master_name or 'Не указан'}</b>\n\n"
            f"Ждём вас! 😊"
        )
        await bot.send_message(client.telegram_id, text)
    except Exception as e:
        logger.error(f"Failed to send reminder to {client.telegram_id}: {e}")
