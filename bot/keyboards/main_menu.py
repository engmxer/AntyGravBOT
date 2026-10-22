"""Main menu keyboard."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config.loader import CompanyConfig


def main_menu_keyboard(cfg: CompanyConfig) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Записаться", callback_data="book:start")
    )
    builder.row(
        InlineKeyboardButton(text="💰 Услуги и цены", callback_data="pricelist:start")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Мои записи", callback_data="my_bookings")
    )
    builder.row(
        InlineKeyboardButton(text="ℹ️ О компании", callback_data="about")
    )
    if cfg.is_feature_enabled("reviews"):
        builder.row(
            InlineKeyboardButton(text="⭐ Отзывы", callback_data="reviews")
        )
    return builder.as_markup()
