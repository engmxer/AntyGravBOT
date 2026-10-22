"""Keyboards for the booking flow."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config.loader import CompanyConfig
from bot.config.schemas import TimeSlot

DAY_NAMES = {
    "mon": "Пн", "tue": "Вт", "wed": "Ср",
    "thu": "Чт", "fri": "Пт", "sat": "Сб", "sun": "Вс",
}
WEEKDAY_MAP = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}


def categories_keyboard(categories: Sequence[Any]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        emoji = getattr(cat, "emoji", "💅")
        name = getattr(cat, "name", "")
        builder.row(
            InlineKeyboardButton(
                text=f"{emoji} {name}",
                callback_data=f"book:cat:{cat.id}",
            )
        )
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def services_keyboard(
    services: Sequence[Any], cfg: CompanyConfig, cat_id: str
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for svc in services:
        price_min = getattr(svc, "price_min", 0)
        price_max = getattr(svc, "price_max", None)
        if price_max and price_max > price_min:
            price_str = f"{price_min}–{price_max} ₽"
        else:
            price_str = f"{price_min} ₽"

        duration = getattr(svc, "duration_minutes", 60)
        builder.row(
            InlineKeyboardButton(
                text=f"{svc.name} — {price_str} ({duration}м)",
                callback_data=f"book:svc:{svc.id}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="book:start"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"),
    )
    return builder.as_markup()


def masters_keyboard(masters: Sequence[Any]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for master in masters:
        name = getattr(master, "name", "")
        spec = getattr(master, "specialty", "")
        label = f"👤 {name}" + (f" ({spec})" if spec else "")
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"book:master:{master.id}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="👥 Любой свободный мастер", callback_data="book:master:any")
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="book:back_to_service"))
    return builder.as_markup()


def calendar_keyboard(
    year: int, month: int, working_days: list[str], prefix: str = "cal"
) -> InlineKeyboardMarkup:
    """Generate inline calendar for a given month with customizable callback prefix."""
    import calendar

    builder = InlineKeyboardBuilder()

    month_names = [
        "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    builder.row(
        InlineKeyboardButton(text="◀", callback_data=f"{prefix}:prev:{year}:{month}"),
        InlineKeyboardButton(
            text=f"{month_names[month]} {year}", callback_data="cal:ignore"
        ),
        InlineKeyboardButton(text="▶", callback_data=f"{prefix}:next:{year}:{month}"),
    )

    headers = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    builder.row(*[InlineKeyboardButton(text=h, callback_data="cal:ignore") for h in headers])

    today = date.today()
    cal = calendar.monthcalendar(year, month)

    for week in cal:
        row_buttons = []
        for weekday_idx, day_num in enumerate(week):
            if day_num == 0:
                row_buttons.append(InlineKeyboardButton(text=" ", callback_data="cal:ignore"))
                continue
            cell_date = date(year, month, day_num)
            day_key = WEEKDAY_MAP[weekday_idx]
            is_past = cell_date < today
            is_working = day_key in working_days
            if is_past or not is_working:
                row_buttons.append(
                    InlineKeyboardButton(text="·", callback_data="cal:ignore")
                )
            else:
                label = str(day_num)
                if cell_date == today:
                    label = f"[{day_num}]"
                row_buttons.append(
                    InlineKeyboardButton(
                        text=label,
                        callback_data=f"{prefix}:date:{cell_date.isoformat()}",
                    )
                )
        builder.row(*row_buttons)

    back_cb = "book:back_to_master" if prefix == "cal" else "my_bookings"
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_cb))
    return builder.as_markup()


def timeslots_keyboard(
    slots: list[TimeSlot], date_str: str, prefix: str = "book"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    available = [s for s in slots if s.is_available]
    if not available:
        builder.row(
            InlineKeyboardButton(text="❌ Нет свободных окон на этот день", callback_data="cal:ignore")
        )
    for slot in available:
        builder.button(
            text=slot.label,
            callback_data=f"{prefix}:time:{slot.start.isoformat()}",
        )
    builder.adjust(4)

    back_cb = "book:back_to_date" if prefix == "book" else f"reschedule:back_to_date"
    builder.row(
        InlineKeyboardButton(text="◀️ Выбрать другой день", callback_data=back_cb)
    )
    return builder.as_markup()


def confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить запись", callback_data="book:confirm"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="main_menu"),
    )
    return builder.as_markup()


def contact_keyboard() -> InlineKeyboardMarkup:
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Отправить мой номер телефона", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
