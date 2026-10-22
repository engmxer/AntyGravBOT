"""Booking flow FSM handlers."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Contact, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.loader import CompanyConfig
from bot.database.repo import BlockedSlotRepo, BookingRepo, CatalogRepo, ClientRepo
from bot.keyboards.booking import (
    calendar_keyboard,
    categories_keyboard,
    confirm_keyboard,
    contact_keyboard,
    masters_keyboard,
    services_keyboard,
    timeslots_keyboard,
)
from bot.keyboards.main_menu import main_menu_keyboard
from bot.states import BookingFSM
from bot.utils.slots import generate_time_slots

logger = logging.getLogger(__name__)
router = Router(name="booking")


# ---------- Entry points ----------

@router.message(Command("book"))
async def cmd_book(
    message: Message,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    await state.clear()
    await state.set_state(BookingFSM.choosing_category)
    catalog_repo = CatalogRepo(session)
    categories = await catalog_repo.get_categories(active_only=True)
    await message.answer(
        "Выберите <b>категорию услуги</b>:",
        reply_markup=categories_keyboard(categories),
    )


@router.callback_query(F.data == "book:start")
async def cb_book_start(
    callback: CallbackQuery,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    await state.clear()
    await state.set_state(BookingFSM.choosing_category)
    catalog_repo = CatalogRepo(session)
    categories = await catalog_repo.get_categories(active_only=True)
    await callback.message.edit_text(
        "Выберите <b>категорию услуги</b>:",
        reply_markup=categories_keyboard(categories),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("book:from_pl:"))
async def cb_book_from_pricelist(
    callback: CallbackQuery,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    """Jump into booking flow with pre-selected service from pricelist."""
    service_id = callback.data.split(":", 2)[2]
    catalog_repo = CatalogRepo(session)
    service = await catalog_repo.get_service(service_id)

    if not service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    await state.clear()
    await state.update_data(
        category_id=service.category_id,
        service_id=service.id,
        service_name=service.name,
        price=service.price_min,
        duration=service.duration_minutes,
    )
    await _proceed_after_service(callback.message, state, company_cfg, session, edit=True)
    await callback.answer()


# ---------- Category selection ----------

@router.callback_query(BookingFSM.choosing_category, F.data.startswith("book:cat:"))
async def cb_choose_category(
    callback: CallbackQuery,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    cat_id = callback.data.split(":", 2)[2]
    catalog_repo = CatalogRepo(session)
    category = await catalog_repo.get_category(cat_id)
    if not category:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    services = await catalog_repo.get_services(category_id=cat_id, active_only=True)
    if not services:
        await callback.answer("В этой категории пока нет услуг", show_alert=True)
        return

    await state.update_data(category_id=cat_id)
    await state.set_state(BookingFSM.choosing_service)
    text = f"{category.emoji} <b>{category.name}</b>\n\nВыберите услугу:"
    await callback.message.edit_text(
        text,
        reply_markup=services_keyboard(services, company_cfg, cat_id),
    )
    await callback.answer()


# ---------- Service selection ----------

@router.callback_query(BookingFSM.choosing_service, F.data.startswith("book:svc:"))
async def cb_choose_service(
    callback: CallbackQuery,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    service_id = callback.data.split(":", 2)[2]
    catalog_repo = CatalogRepo(session)
    service = await catalog_repo.get_service(service_id)
    if not service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    await state.update_data(
        service_id=service.id,
        service_name=service.name,
        price=service.price_min,
        duration=service.duration_minutes,
    )
    await _proceed_after_service(callback.message, state, company_cfg, session, edit=True)
    await callback.answer()


async def _proceed_after_service(
    message: Message,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
    edit: bool = False,
) -> None:
    """Route to master selection or directly to calendar."""
    catalog_repo = CatalogRepo(session)
    masters = list(await catalog_repo.get_masters(active_only=True))

    if company_cfg.is_feature_enabled("master_selection") and len(masters) > 1:
        await state.set_state(BookingFSM.choosing_master)
        text = "Выберите <b>мастера</b>:"
        if edit:
            await message.edit_text(text, reply_markup=masters_keyboard(masters))
        else:
            await message.answer(text, reply_markup=masters_keyboard(masters))
    else:
        # Default or single master
        if masters:
            await state.update_data(master_id=masters[0].id, master_name=masters[0].name)
        else:
            await state.update_data(master_id=None, master_name=None)
        await _show_calendar(message, state, company_cfg, edit=edit)


# ---------- Master selection ----------

@router.callback_query(BookingFSM.choosing_master, F.data.startswith("book:master:"))
async def cb_choose_master(
    callback: CallbackQuery,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    master_raw = callback.data.split(":", 2)[2]
    if master_raw == "any":
        await state.update_data(master_id=None, master_name="Любой мастер")
    else:
        catalog_repo = CatalogRepo(session)
        master = await catalog_repo.get_master(master_raw)
        if master:
            await state.update_data(master_id=master.id, master_name=master.name)
    await _show_calendar(callback.message, state, company_cfg, edit=True)
    await callback.answer()


# ---------- Calendar ----------

async def _show_calendar(
    message: Message,
    state: FSMContext,
    company_cfg: CompanyConfig,
    edit: bool = False,
) -> None:
    await state.set_state(BookingFSM.choosing_date)
    today = date.today()
    kb = calendar_keyboard(today.year, today.month, company_cfg.working_days, prefix="cal")
    text = "📅 Выберите <b>дату</b> записи:\n<i>(Рабочие дни отмечены числами, выходные — точками)</i>"
    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("cal:prev:"))
async def cb_cal_prev(
    callback: CallbackQuery, state: FSMContext, company_cfg: CompanyConfig
) -> None:
    _, _, year_s, month_s = callback.data.split(":")
    year, month = int(year_s), int(month_s)
    month -= 1
    if month < 1:
        month = 12
        year -= 1
    today = date.today()
    if date(year, month, 1) < date(today.year, today.month, 1):
        await callback.answer("Нельзя выбрать прошедший месяц", show_alert=True)
        return
    kb = calendar_keyboard(year, month, company_cfg.working_days, prefix="cal")
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("cal:next:"))
async def cb_cal_next(
    callback: CallbackQuery, state: FSMContext, company_cfg: CompanyConfig
) -> None:
    _, _, year_s, month_s = callback.data.split(":")
    year, month = int(year_s), int(month_s)
    month += 1
    if month > 12:
        month = 1
        year += 1
    kb = calendar_keyboard(year, month, company_cfg.working_days, prefix="cal")
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "cal:ignore")
async def cb_cal_ignore(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(BookingFSM.choosing_date, F.data.startswith("cal:date:"))
async def cb_choose_date(
    callback: CallbackQuery,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    date_str = callback.data.split(":", 2)[2]
    chosen_date = date.fromisoformat(date_str)
    data = await state.get_data()
    duration = data.get("duration", 60)
    master_id = data.get("master_id")

    booking_repo = BookingRepo(session)
    block_repo = BlockedSlotRepo(session)
    bookings = await booking_repo.get_bookings_for_date(chosen_date, master_id)
    blocked = await block_repo.get_blocked(chosen_date, master_id)

    full_day_blocked = any(b.start_time is None for b in blocked)
    if full_day_blocked:
        await callback.answer("Этот день недоступен (выходной/отпуск/блокировка)", show_alert=True)
        return

    slots = generate_time_slots(
        chosen_date=chosen_date,
        company_cfg=company_cfg,
        duration_minutes=duration,
        existing_bookings=[(b.starts_at, b.ends_at) for b in bookings],
        blocked_ranges=[(b.start_time, b.end_time) for b in blocked if b.start_time],
    )

    await state.update_data(chosen_date=date_str)
    await state.set_state(BookingFSM.choosing_time)

    text = f"🕐 Выберите <b>свободное время</b> на <b>{chosen_date.strftime('%d.%m.%Y')}</b>:"
    await callback.message.edit_text(text, reply_markup=timeslots_keyboard(slots, date_str, prefix="book"))
    await callback.answer()


# ---------- Time selection ----------

@router.callback_query(BookingFSM.choosing_time, F.data.startswith("book:time:"))
async def cb_choose_time(
    callback: CallbackQuery, state: FSMContext, company_cfg: CompanyConfig
) -> None:
    time_str = callback.data.split(":", 2)[2]
    starts_at = datetime.fromisoformat(time_str)
    await state.update_data(starts_at=time_str)
    await state.set_state(BookingFSM.confirming)

    data = await state.get_data()
    text = _format_booking_summary(data, starts_at, company_cfg)
    await callback.message.edit_text(text, reply_markup=confirm_keyboard())
    await callback.answer()


def _format_booking_summary(data: dict, starts_at: datetime, cfg: CompanyConfig) -> str:
    duration = data.get("duration", 60)
    ends_at = starts_at + timedelta(minutes=duration)
    price = data.get("price", 0)
    master_name = data.get("master_name", "Любой свободный мастер")
    return (
        f"<b>📋 Проверьте данные вашей записи:</b>\n\n"
        f"💅 Услуга: <b>{data.get('service_name', '—')}</b>\n"
        f"👤 Мастер: <b>{master_name}</b>\n"
        f"📅 Дата: <b>{starts_at.strftime('%d.%m.%Y')}</b>\n"
        f"🕐 Время: <b>{starts_at.strftime('%H:%M')} – {ends_at.strftime('%H:%M')}</b>\n"
        f"⏱ Длительность: <b>{duration} мин</b>\n"
        f"💰 Стоимость: <b>{price} ₽</b>\n\n"
        "Всё верно? Нажмите «Подтвердить запись» для завершения."
    )


# ---------- Confirmation ----------

@router.callback_query(BookingFSM.confirming, F.data == "book:confirm")
async def cb_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    # Check if client already exists and has a phone number
    client_repo = ClientRepo(session)
    client = await client_repo.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
    )

    if client.phone:
        await state.update_data(
            client_name=client.full_name or callback.from_user.first_name or "Клиент",
            client_phone=client.phone,
        )
        await _finalize_booking(callback.message, state, company_cfg, callback.from_user, session)
        await callback.answer()
        return

    full_name = (
        f"{callback.from_user.first_name or ''} {callback.from_user.last_name or ''}".strip()
    )
    if full_name:
        await state.update_data(client_name=full_name)
        await state.set_state(BookingFSM.entering_phone)
        await callback.message.edit_text(
            f"Ваше имя: <b>{full_name}</b>\n\nПожалуйста, отправьте контактный номер телефона для связи:",
            reply_markup=None,
        )
        await callback.message.answer(
            "Нажмите кнопку ниже или введите номер вручную:",
            reply_markup=contact_keyboard(),
        )
    else:
        await state.set_state(BookingFSM.entering_name)
        await callback.message.edit_text(
            "Введите ваше имя:", reply_markup=None
        )
    await callback.answer()


@router.message(BookingFSM.entering_name)
async def msg_enter_name(message: Message, state: FSMContext) -> None:
    await state.update_data(client_name=message.text.strip())
    await state.set_state(BookingFSM.entering_phone)
    await message.answer(
        "Спасибо! Теперь отправьте контактный номер телефона:",
        reply_markup=contact_keyboard(),
    )


@router.message(BookingFSM.entering_phone, F.contact)
async def msg_contact(
    message: Message,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    contact: Contact = message.contact
    await state.update_data(client_phone=contact.phone_number)
    await message.answer("✅ Номер получен!", reply_markup=ReplyKeyboardRemove())
    await _finalize_booking(message, state, company_cfg, message.from_user, session)


@router.message(BookingFSM.entering_phone)
async def msg_phone_text(
    message: Message,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    await state.update_data(client_phone=message.text.strip())
    await message.answer("✅ Номер сохранён!", reply_markup=ReplyKeyboardRemove())
    await _finalize_booking(message, state, company_cfg, message.from_user, session)


async def _finalize_booking(
    message: Message,
    state: FSMContext,
    company_cfg: CompanyConfig,
    tg_user: Any,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    client_repo = ClientRepo(session)
    booking_repo = BookingRepo(session)

    client = await client_repo.get_or_create(
        telegram_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
    )
    phone = data.get("client_phone", client.phone or "")
    client_name = data.get("client_name", client.full_name or tg_user.first_name or "")
    await client_repo.update_contact(tg_user.id, phone, client_name)

    starts_at = datetime.fromisoformat(data["starts_at"])
    booking = await booking_repo.create_booking(
        client_id=client.id,
        category_id=data.get("category_id", ""),
        service_id=data["service_id"],
        service_name=data["service_name"],
        master_id=data.get("master_id"),
        master_name=data.get("master_name"),
        price=data.get("price", 0),
        duration_minutes=data.get("duration", 60),
        starts_at=starts_at,
    )
    await session.commit()

    duration = data.get("duration", 60)
    ends_at = starts_at + timedelta(minutes=duration)
    confirm_text = (
        f"🎉 <b>Запись успешно создана!</b>\n\n"
        f"💅 Услуга: <b>{data['service_name']}</b>\n"
        f"👤 Мастер: <b>{data.get('master_name', 'Любой свободный мастер')}</b>\n"
        f"📅 Дата: <b>{starts_at.strftime('%d.%m.%Y')}</b>\n"
        f"🕐 Время: <b>{starts_at.strftime('%H:%M')} – {ends_at.strftime('%H:%M')}</b>\n"
        f"💰 Стоимость: <b>{data.get('price', 0)} ₽</b>\n"
        f"📞 Контактный номер: <b>{phone}</b>\n\n"
        f"Ждём вас по адресу:\n📍 {company_cfg.address}\n\n"
        f"Управлять записью (отменить или перенести) вы всегда можете в меню <b>«📋 Мои записи»</b>."
    )
    await message.answer(confirm_text, reply_markup=main_menu_keyboard(company_cfg))
    await state.clear()

    # Notify admin
    from bot.utils.notifications import notify_admin_new_booking
    await notify_admin_new_booking(message.bot, booking, client, company_cfg)


# ---------- Back navigation ----------

@router.callback_query(F.data == "book:back_to_service")
async def cb_back_to_service(
    callback: CallbackQuery,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    cat_id = data.get("category_id")
    catalog_repo = CatalogRepo(session)

    if not cat_id:
        await state.set_state(BookingFSM.choosing_category)
        categories = await catalog_repo.get_categories(active_only=True)
        await callback.message.edit_text(
            "Выберите категорию:",
            reply_markup=categories_keyboard(categories),
        )
    else:
        category = await catalog_repo.get_category(cat_id)
        services = await catalog_repo.get_services(category_id=cat_id, active_only=True)
        await state.set_state(BookingFSM.choosing_service)
        cat_name = category.name if category else ""
        cat_emoji = category.emoji if category else "💅"
        await callback.message.edit_text(
            f"{cat_emoji} <b>{cat_name}</b>\n\nВыберите услугу:",
            reply_markup=services_keyboard(services, company_cfg, cat_id),
        )
    await callback.answer()


@router.callback_query(F.data == "book:back_to_master")
async def cb_back_to_master(
    callback: CallbackQuery,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    catalog_repo = CatalogRepo(session)
    masters = list(await catalog_repo.get_masters(active_only=True))
    if company_cfg.is_feature_enabled("master_selection") and len(masters) > 1:
        await state.set_state(BookingFSM.choosing_master)
        await callback.message.edit_text(
            "Выберите мастера:", reply_markup=masters_keyboard(masters)
        )
    else:
        await cb_back_to_service(callback, state, company_cfg, session)
    await callback.answer()


@router.callback_query(F.data == "book:back_to_date")
async def cb_back_to_date(
    callback: CallbackQuery, state: FSMContext, company_cfg: CompanyConfig
) -> None:
    await _show_calendar(callback.message, state, company_cfg, edit=True)
    await callback.answer()
