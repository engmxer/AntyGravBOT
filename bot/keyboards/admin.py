"""Admin panel keyboards."""
from __future__ import annotations

from typing import Any, Sequence
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📅 Записи на сегодня", callback_data="admin:today"))
    builder.row(InlineKeyboardButton(text="📆 Записи на неделю", callback_data="admin:week"))
    builder.row(InlineKeyboardButton(text="💰 Управление прайс-листом", callback_data="admin:catalog"))
    builder.row(
        InlineKeyboardButton(text="🚫 Блокировка дня", callback_data="admin:block_day"),
        InlineKeyboardButton(text="🔓 Разблокировка дня", callback_data="admin:unblock_day"),
    )
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def admin_catalog_categories_keyboard(categories: Sequence[Any]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        emoji = getattr(cat, "emoji", "💅")
        name = getattr(cat, "name", "")
        builder.row(
            InlineKeyboardButton(
                text=f"{emoji} {name}",
                callback_data=f"admin:cat:{cat.id}",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад в админку", callback_data="admin:menu"))
    return builder.as_markup()


def admin_category_services_keyboard(
    cat_id: str, services: Sequence[Any]
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for svc in services:
        status = "🟢" if svc.is_active else "🔴"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {svc.name} — {svc.price_min}₽",
                callback_data=f"admin:svc:{svc.id}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить услугу", callback_data=f"admin:add_svc:{cat_id}")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ К категориям", callback_data="admin:catalog"),
        InlineKeyboardButton(text="👑 В админку", callback_data="admin:menu"),
    )
    return builder.as_markup()


def admin_service_manage_keyboard(service_id: str, cat_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Изменить цену", callback_data=f"admin:edit_price:{service_id}"),
        InlineKeyboardButton(text="🔄 Вкл/Выкл", callback_data=f"admin:toggle_svc:{service_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить услугу", callback_data=f"admin:delete_svc:{service_id}")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад к списку", callback_data=f"admin:cat:{cat_id}"),
        InlineKeyboardButton(text="👑 В админку", callback_data="admin:menu"),
    )
    return builder.as_markup()


def admin_cancel_booking_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❌ Отменить эту запись", callback_data=f"admin:cancel_bk:{booking_id}")
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:today"))
    return builder.as_markup()
