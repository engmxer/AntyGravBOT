"""My bookings handlers: view, cancel, and reschedule bookings."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.loader import CompanyConfig
from bot.database.repo import BlockedSlotRepo, BookingRepo, ClientRepo
from bot.keyboards.booking import calendar_keyboard, timeslots_keyboard
from bot.keyboards.main_menu import main_menu_keyboard
from bot.states import RescheduleFSM
from bot.utils.slots import generate_time_slots

logger = logging.getLogger(__name__)
router = Router(name="my_bookings")


@router.message(Command("mybookings"))
async def cmd_my_bookings(
    message: Message,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    await state.clear()
    await _show_my_bookings(message, company_cfg, session, message.from_user.id, edit=False)


@router.callback_query(F.data == "my_bookings")
async def cb_my_bookings(
    callback: CallbackQuery,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    await state.clear()
    await _show_my_bookings(callback.message, company_cfg, session, callback.from_user.id, edit=True)
    await callback.answer()


async def _show_my_bookings(
    message: Message,
    company_cfg: CompanyConfig,
    session: AsyncSession,
    telegram_id: int,
    edit: bool = False,
) -> None:
    client_repo = ClientRepo(session)
    booking_repo = BookingRepo(session)
    client = await client_repo.get_or_create(telegram_id=telegram_id)
    bookings = await booking_repo.get_client_bookings(client.id, only_upcoming=True)

    builder = InlineKeyboardBuilder()
    if not bookings:
        text = "📋 <b>У вас нет предстоящих записей.</b>\n\nВы можете записаться на услугу в удобное для вас время:"
        builder.row(InlineKeyboardButton(text="📅 Записаться", callback_data="book:start"))
    else:
        lines = ["<b>📋 Ваши предстоящие записи:</b>\n"]
        for b in bookings:
            dt = b.starts_at.strftime("%d.%m.%Y %H:%M")
            lines.append(
                f"💅 <b>{b.service_name}</b>\n"
                f"   📅 <b>{dt}</b>\n"
                f"   👤 Мастер: {b.master_name or 'Любой свободный мастер'}\n"
                f"   💰 {b.price} ₽ | ⏱ {b.duration_minutes} мин\n"
            )
            # Two action buttons per booking: Reschedule & Cancel
            builder.row(
                InlineKeyboardButton(
                    text=f"🔄 Перенести ({dt})",
                    callback_data=f"reschedule:start:{b.id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=f"cancel_booking:{b.id}",
                ),
            )
        text = "\n".join(lines)

    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))

    if edit:
        await message.edit_text(text, reply_markup=builder.as_markup())
    else:
        await message.answer(text, reply_markup=builder.as_markup())


# ---------- Cancellation ----------

@router.callback_query(F.data.startswith("cancel_booking:"))
async def cb_cancel_booking(
    callback: CallbackQuery,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    booking_id = int(callback.data.split(":", 1)[1])
    client_repo = ClientRepo(session)
    booking_repo = BookingRepo(session)
    client = await client_repo.get_or_create(telegram_id=callback.from_user.id)
    cancelled = await booking_repo.cancel_booking(booking_id, client.id)
    await session.commit()

    if cancelled:
        await callback.answer("✅ Запись успешно отменена", show_alert=True)
    else:
        await callback.answer("❌ Не удалось отменить запись", show_alert=True)

    await _show_my_bookings(
        callback.message, company_cfg, session, callback.from_user.id, edit=True
    )


# ---------- Rescheduling Flow ----------

@router.callback_query(F.data.startswith("reschedule:start:"))
async def cb_reschedule_start(
    callback: CallbackQuery,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    booking_id = int(callback.data.split(":", 2)[2])
    booking_repo = BookingRepo(session)
    booking = await booking_repo.get_booking_by_id(booking_id)

    if not booking:
        await callback.answer("Запись не найдена", show_alert=True)
        return

    await state.set_state(RescheduleFSM.choosing_date)
    await state.update_data(
        booking_id=booking.id,
        duration=booking.duration_minutes,
        master_id=booking.master_id,
        service_name=booking.service_name,
        old_starts_at=booking.starts_at.isoformat(),
    )

    today = date.today()
    kb = calendar_keyboard(today.year, today.month, company_cfg.working_days, prefix="rcal")
    text = (
        f"🔄 <b>Перенос записи: {booking.service_name}</b>\n"
        f"Текущее время: {booking.starts_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"📅 Выберите <b>новую дату</b>:"
    )
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("rcal:prev:"))
async def cb_rcal_prev(
    callback: CallbackQuery, company_cfg: CompanyConfig
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
    kb = calendar_keyboard(year, month, company_cfg.working_days, prefix="rcal")
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("rcal:next:"))
async def cb_rcal_next(
    callback: CallbackQuery, company_cfg: CompanyConfig
) -> None:
    _, _, year_s, month_s = callback.data.split(":")
    year, month = int(year_s), int(month_s)
    month += 1
    if month > 12:
        month = 1
        year += 1
    kb = calendar_keyboard(year, month, company_cfg.working_days, prefix="rcal")
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(RescheduleFSM.choosing_date, F.data.startswith("rcal:date:"))
async def cb_rcal_date(
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
        await callback.answer("Этот день недоступен для записи", show_alert=True)
        return

    # Exclude the current booking being rescheduled from collision check
    current_bid = data.get("booking_id")
    other_bookings = [
        (b.starts_at, b.ends_at) for b in bookings if b.id != current_bid
    ]

    slots = generate_time_slots(
        chosen_date=chosen_date,
        company_cfg=company_cfg,
        duration_minutes=duration,
        existing_bookings=other_bookings,
        blocked_ranges=[(b.start_time, b.end_time) for b in blocked if b.start_time],
    )

    await state.update_data(new_date=date_str)
    await state.set_state(RescheduleFSM.choosing_time)

    text = f"🕐 Выберите <b>новое время</b> на <b>{chosen_date.strftime('%d.%m.%Y')}</b>:"
    await callback.message.edit_text(
        text, reply_markup=timeslots_keyboard(slots, date_str, prefix="reschedule")
    )
    await callback.answer()


@router.callback_query(RescheduleFSM.choosing_time, F.data.startswith("reschedule:time:"))
async def cb_rcal_time(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    time_str = callback.data.split(":", 2)[2]
    new_starts_at = datetime.fromisoformat(time_str)
    await state.update_data(new_starts_at=time_str)
    await state.set_state(RescheduleFSM.confirming)

    data = await state.get_data()
    duration = data.get("duration", 60)
    new_ends_at = new_starts_at + timedelta(minutes=duration)
    old_starts_at = datetime.fromisoformat(data["old_starts_at"])

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить перенос", callback_data="reschedule:confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="my_bookings"),
    )

    text = (
        f"<b>🔄 Подтверждение переноса записи:</b>\n\n"
        f"💅 Услуга: <b>{data.get('service_name')}</b>\n"
        f"Было: <s>{old_starts_at.strftime('%d.%m.%Y %H:%M')}</s>\n"
        f"Станет: <b>{new_starts_at.strftime('%d.%m.%Y')} с {new_starts_at.strftime('%H:%M')} до {new_ends_at.strftime('%H:%M')}</b>\n\n"
        "Перенести запись на это время?"
    )
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(RescheduleFSM.confirming, F.data == "reschedule:confirm")
async def cb_rcal_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    company_cfg: CompanyConfig,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    booking_id = data["booking_id"]
    new_starts_at = datetime.fromisoformat(data["new_starts_at"])

    client_repo = ClientRepo(session)
    booking_repo = BookingRepo(session)
    client = await client_repo.get_or_create(telegram_id=callback.from_user.id)

    updated_booking = await booking_repo.reschedule_booking(
        booking_id=booking_id,
        client_id=client.id,
        new_starts_at=new_starts_at,
    )
    await session.commit()
    await state.clear()

    if updated_booking:
        await callback.message.edit_text(
            f"🎉 <b>Запись успешно перенесена!</b>\n\n"
            f"💅 Услуга: <b>{updated_booking.service_name}</b>\n"
            f"📅 Новая дата: <b>{new_starts_at.strftime('%d.%m.%Y')}</b>\n"
            f"🕐 Время: <b>{new_starts_at.strftime('%H:%M')} – {updated_booking.ends_at.strftime('%H:%M')}</b>\n\n"
            "Ждем вас в назначенное время!",
            reply_markup=main_menu_keyboard(company_cfg),
        )
    else:
        await callback.answer("Ошибка при переносе", show_alert=True)
        await _show_my_bookings(callback.message, company_cfg, session, callback.from_user.id, edit=True)
    await callback.answer()
