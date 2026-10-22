"""Pricelist browsing handlers with categories, sorting, and direct booking."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.loader import CompanyConfig
from bot.database.repo import CatalogRepo
from bot.keyboards.pricelist import (
    category_services_keyboard,
    format_service_price,
    pricelist_categories_keyboard,
    service_card_keyboard,
)
from bot.states import PricelistFSM

logger = logging.getLogger(__name__)
router = Router(name="pricelist")


@router.message(Command("prices"))
async def cmd_prices(
    message: Message,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    await state.clear()
    await state.set_state(PricelistFSM.browsing_categories)
    catalog_repo = CatalogRepo(session)
    categories = await catalog_repo.get_categories(active_only=True)

    text = f"💰 <b>Прайс-лист и услуги</b>\n\nВыберите категорию для просмотра:"
    await message.answer(
        text,
        reply_markup=pricelist_categories_keyboard(categories),
    )


@router.callback_query(F.data == "pricelist:start")
async def cb_pricelist_start(
    callback: CallbackQuery,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    await state.set_state(PricelistFSM.browsing_categories)
    catalog_repo = CatalogRepo(session)
    categories = await catalog_repo.get_categories(active_only=True)

    text = f"💰 <b>Прайс-лист и услуги</b>\n\nВыберите категорию для просмотра:"
    await callback.message.edit_text(
        text,
        reply_markup=pricelist_categories_keyboard(categories),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pl:cat:"))
async def cb_pl_category(
    callback: CallbackQuery,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    cat_id = callback.data.split(":", 2)[2]
    await _show_category_services(callback, state, session, cat_id=cat_id, sort_by=None)
    await callback.answer()


@router.callback_query(F.data.startswith("pl:sort:"))
async def cb_pl_sort(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    _, _, cat_id, sort_by = callback.data.split(":")
    await _show_category_services(callback, state, session, cat_id=cat_id, sort_by=sort_by)
    await callback.answer()


@router.callback_query(F.data.startswith("pl:nav:"))
async def cb_pl_nav(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    cat_idx = int(callback.data.split(":", 2)[2])
    catalog_repo = CatalogRepo(session)
    categories = await catalog_repo.get_categories(active_only=True)
    if 0 <= cat_idx < len(categories):
        target_cat = categories[cat_idx]
        await _show_category_services(callback, state, session, cat_id=target_cat.id, sort_by=None)
    await callback.answer()


async def _show_category_services(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    cat_id: str,
    sort_by: str | None = None,
) -> None:
    catalog_repo = CatalogRepo(session)
    categories = list(await catalog_repo.get_categories(active_only=True))
    category = await catalog_repo.get_category(cat_id)

    if not category:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    cat_idx = next((i for i, c in enumerate(categories) if c.id == cat_id), 0)
    services = await catalog_repo.get_services(category_id=cat_id, active_only=True, sort_by=sort_by)

    lines = [f"{category.emoji} <b>{category.name}</b>\n"]
    if not services:
        lines.append("<i>В данной категории пока нет активных услуг.</i>")
    else:
        lines.append("Нажмите на услугу ниже, чтобы посмотреть подробности или сразу записаться:\n")
        for svc in services:
            price_str = format_service_price(svc.price_min, svc.price_max)
            lines.append(f"• <b>{svc.name}</b> — {price_str} ({svc.duration_minutes} мин)")
            if svc.description:
                lines.append(f"  <i>{svc.description}</i>")

    text = "\n".join(lines)
    kb = category_services_keyboard(
        cat_id=cat_id,
        services=services,
        cat_idx=cat_idx,
        total_cats=len(categories),
        sort_by=sort_by,
    )
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("pl:svc:"))
async def cb_pl_service_card(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    service_id = callback.data.split(":", 2)[2]
    catalog_repo = CatalogRepo(session)
    service = await catalog_repo.get_service(service_id)

    if not service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    await state.set_state(PricelistFSM.viewing_service_card)
    price_str = format_service_price(service.price_min, service.price_max)

    text = (
        f"<b>{service.name}</b>\n\n"
        f"💰 <b>Стоимость:</b> {price_str}\n"
        f"⏱ <b>Длительность:</b> {service.duration_minutes} минут\n"
    )
    if service.description:
        text += f"\n📝 <b>Описание:</b>\n{service.description}\n"

    kb = service_card_keyboard(service_id=service.id, cat_id=service.category_id)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()
