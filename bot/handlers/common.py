"""Common handlers: /start, /help, about, main menu."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config.loader import CompanyConfig
from bot.keyboards.main_menu import main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router(name="common")


@router.message(Command("start"))
async def cmd_start(message: Message, company_cfg: CompanyConfig, state: FSMContext) -> None:
    await state.clear()
    text = company_cfg.get_text(
        "welcome",
        name=company_cfg.name,
        emoji=company_cfg.emoji,
        tagline=company_cfg.tagline,
    )
    await message.answer(text, reply_markup=main_menu_keyboard(company_cfg))


@router.message(Command("help"))
async def cmd_help(message: Message, company_cfg: CompanyConfig) -> None:
    text = (
        f"<b>{company_cfg.emoji} {company_cfg.name}</b>\n\n"
        "Доступные команды:\n"
        "/start — главное меню\n"
        "/book — записаться на услугу\n"
        "/prices — услуги и цены\n"
        "/mybookings — мои записи\n"
        "/admin — панель администратора (для админов)\n"
    )
    await message.answer(text)


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, company_cfg: CompanyConfig, state: FSMContext) -> None:
    await state.clear()
    text = company_cfg.get_text(
        "welcome",
        name=company_cfg.name,
        emoji=company_cfg.emoji,
        tagline=company_cfg.tagline,
    )
    await callback.message.edit_text(text, reply_markup=main_menu_keyboard(company_cfg))
    await callback.answer()


@router.callback_query(F.data == "about")
async def cb_about(callback: CallbackQuery, company_cfg: CompanyConfig) -> None:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    cfg = company_cfg
    days_map = {
        "mon": "Понедельник", "tue": "Вторник", "wed": "Среда",
        "thu": "Четверг", "fri": "Пятница", "sat": "Суббота", "sun": "Воскресенье",
    }
    hours_default = cfg.working_hours.get("default")
    schedule_str = ""
    if hours_default:
        days_ru = [days_map.get(d, d) for d in cfg.working_days]
        schedule_str = (
            f"🕐 Режим работы: {', '.join(days_ru)}\n"
            f"   {hours_default.start} – {hours_default.end}"
        )

    text = (
        f"<b>{cfg.emoji} {cfg.name}</b>\n"
        f"{cfg.tagline}\n\n"
        f"📍 Адрес: {cfg.address}\n"
        f"📞 Телефон: {cfg.phone}\n"
    )
    if cfg.instagram:
        text += f"📸 Instagram: {cfg.instagram}\n"
    if cfg.website:
        text += f"🌐 Сайт: {cfg.website}\n"
    text += f"\n{schedule_str}"

    builder = InlineKeyboardBuilder()
    if cfg.maps_link:
        builder.row(InlineKeyboardButton(text="🗺 Открыть на карте", url=cfg.maps_link))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "reviews")
async def cb_reviews(callback: CallbackQuery, company_cfg: CompanyConfig) -> None:
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    reviews_url = company_cfg.texts.get("reviews_url", "")
    builder = InlineKeyboardBuilder()
    if reviews_url:
        builder.row(InlineKeyboardButton(text="⭐ Читать отзывы", url=reviews_url))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))

    text = company_cfg.get_text("reviews_text")
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()
