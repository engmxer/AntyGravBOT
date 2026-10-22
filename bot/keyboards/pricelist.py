"""Keyboards for the pricelist flow."""
from __future__ import annotations

from typing import Any, Sequence
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def format_service_price(price_min: int, price_max: int | None = None) -> str:
    if price_max and price_max > price_min:
        return f"{price_min}–{price_max} ₽"
    return f"{price_min} ₽"


def pricelist_categories_keyboard(
    categories: Sequence[Any], current_cat_id: str | None = None
) -> InlineKeyboardMarkup:
    """List of all categories for browsing."""
    builder = InlineKeyboardBuilder()
    for cat in categories:
        mark = "👉 " if current_cat_id and cat.id == current_cat_id else ""
        emoji = getattr(cat, "emoji", "💅")
        name = getattr(cat, "name", "")
        builder.row(
            InlineKeyboardButton(
                text=f"{mark}{emoji} {name}",
                callback_data=f"pl:cat:{cat.id}",
            )
        )
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def category_services_keyboard(
    cat_id: str,
    services: Sequence[Any],
    cat_idx: int,
    total_cats: int,
    sort_by: str | None = None,
) -> InlineKeyboardMarkup:
    """List of services in a category with sorting and direct booking options."""
    builder = InlineKeyboardBuilder()

    # Sort toggles
    sort_label_asc = "🟢 Дешевле" if sort_by == "price_asc" else "⬆️ По цене (мин)"
    sort_label_desc = "🟢 Дороже" if sort_by == "price_desc" else "⬇️ По цене (макс)"
    builder.row(
        InlineKeyboardButton(text=sort_label_asc, callback_data=f"pl:sort:{cat_id}:price_asc"),
        InlineKeyboardButton(text=sort_label_desc, callback_data=f"pl:sort:{cat_id}:price_desc"),
    )

    # Service item buttons (clicking opens full service details card)
    for svc in services:
        price_str = format_service_price(svc.price_min, getattr(svc, "price_max", None))
        duration = getattr(svc, "duration_minutes", 60)
        builder.row(
            InlineKeyboardButton(
                text=f"{svc.name} — {price_str} ({duration}м)",
                callback_data=f"pl:svc:{svc.id}",
            )
        )

    # Category navigation arrows
    nav_buttons = []
    if cat_idx > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️ Пред. категория", callback_data=f"pl:nav:{cat_idx - 1}")
        )
    if cat_idx < total_cats - 1:
        nav_buttons.append(
            InlineKeyboardButton(text="След. категория ▶️", callback_data=f"pl:nav:{cat_idx + 1}")
        )
    if nav_buttons:
        builder.row(*nav_buttons)

    # Return buttons
    builder.row(
        InlineKeyboardButton(text="🗂 Все категории", callback_data="pricelist:start"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
    )
    return builder.as_markup()


def service_card_keyboard(service_id: str, cat_id: str) -> InlineKeyboardMarkup:
    """Action buttons on a single service details card."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📅 Записаться на эту услугу",
            callback_data=f"book:from_pl:{service_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад к категории", callback_data=f"pl:cat:{cat_id}"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
    )
    return builder.as_markup()
