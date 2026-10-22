"""Admin panel handlers: scheduling, bookings overview, price-list CRUD, and day blocking."""
from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.loader import EnvConfig
from bot.database.repo import BlockedSlotRepo, BookingRepo, CatalogRepo
from bot.keyboards.admin import (
    admin_cancel_booking_keyboard,
    admin_catalog_categories_keyboard,
    admin_category_services_keyboard,
    admin_menu_keyboard,
    admin_service_manage_keyboard,
)
from bot.states import AdminFSM

logger = logging.getLogger(__name__)
router = Router(name="admin")


def is_admin(user_id: int, env_cfg: EnvConfig) -> bool:
    return user_id in env_cfg.admin_ids


@router.message(Command("admin"))
async def cmd_admin(
    message: Message, env_cfg: EnvConfig, state: FSMContext
) -> None:
    if not is_admin(message.from_user.id, env_cfg):
        await message.answer("❌ У вас нет прав администратора.")
        return
    await state.clear()
    await state.set_state(AdminFSM.main_menu)
    await message.answer(
        "👑 <b>Панель управления администратора</b>\n\n"
        "Выберите раздел для работы:",
        reply_markup=admin_menu_keyboard(),
    )


@router.callback_query(F.data == "admin:menu")
async def cb_admin_menu(
    callback: CallbackQuery, env_cfg: EnvConfig, state: FSMContext
) -> None:
    if not is_admin(callback.from_user.id, env_cfg):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.clear()
    await state.set_state(AdminFSM.main_menu)
    await callback.message.edit_text(
        "👑 <b>Панель управления администратора</b>\n\n"
        "Выберите раздел для работы:",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


# ---------- Bookings: Today & Week ----------

@router.callback_query(F.data == "admin:today")
async def cb_admin_today(
    callback: CallbackQuery,
    env_cfg: EnvConfig,
    session: AsyncSession,
) -> None:
    if not is_admin(callback.from_user.id, env_cfg):
        await callback.answer("Нет доступа", show_alert=True)
        return

    today = date.today()
    booking_repo = BookingRepo(session)
    bookings = await booking_repo.get_bookings_for_date(today)

    builder = InlineKeyboardBuilder()
    if not bookings:
        text = f"📅 <b>Записи на сегодня ({today.strftime('%d.%m.%Y')}):</b>\n\nЗаписей нет."
    else:
        lines = [f"📅 <b>Записи на сегодня ({today.strftime('%d.%m.%Y')}):</b>\n"]
        for b in bookings:
            t = b.starts_at.strftime("%H:%M")
            lines.append(
                f"🕐 <b>{t}</b> — {b.service_name}\n"
                f"   👤 Клиент: {b.client.full_name or b.client.first_name or 'Без имени'} ({b.client.phone or 'без тел.'})\n"
                f"   👨‍💼 Мастер: {b.master_name or 'Любой'}\n"
                f"   💰 {b.price} ₽ | #{b.id}\n"
            )
            builder.row(
                InlineKeyboardButton(
                    text=f"❌ Отменить #{b.id} ({t})",
                    callback_data=f"admin:cancel_bk:{b.id}",
                )
            )
        text = "\n".join(lines)

    builder.row(InlineKeyboardButton(text="◀️ Назад в админку", callback_data="admin:menu"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin:week")
async def cb_admin_week(
    callback: CallbackQuery,
    env_cfg: EnvConfig,
    session: AsyncSession,
) -> None:
    if not is_admin(callback.from_user.id, env_cfg):
        await callback.answer("Нет доступа", show_alert=True)
        return

    today = date.today()
    booking_repo = BookingRepo(session)
    bookings = await booking_repo.get_week_bookings(today)

    if not bookings:
        text = "📆 <b>Записи на ближайшие 7 дней:</b>\n\nЗаписей нет."
    else:
        lines = ["📆 <b>Записи на ближайшие 7 дней:</b>\n"]
        current_day = None
        for b in bookings:
            day_str = b.starts_at.strftime("%d.%m.%Y")
            if day_str != current_day:
                lines.append(f"\n📅 <b>{day_str}:</b>")
                current_day = day_str
            t = b.starts_at.strftime("%H:%M")
            client_name = b.client.full_name or b.client.first_name if b.client else "Клиент"
            lines.append(f"  • {t} — {b.service_name} ({client_name}, {b.master_name or 'Любой'})")
        text = "\n".join(lines)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад в админку", callback_data="admin:menu"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:cancel_bk:"))
async def cb_admin_cancel_booking(
    callback: CallbackQuery,
    env_cfg: EnvConfig,
    session: AsyncSession,
) -> None:
    if not is_admin(callback.from_user.id, env_cfg):
        await callback.answer("Нет доступа", show_alert=True)
        return
    booking_id = int(callback.data.split(":", 2)[2])
    booking_repo = BookingRepo(session)
    success = await booking_repo.cancel_booking(booking_id)
    await session.commit()
    if success:
        await callback.answer(f"Запись #{booking_id} отменена", show_alert=True)
    else:
        await callback.answer("Не удалось отменить запись", show_alert=True)
    await cb_admin_today(callback, env_cfg, session)


# ---------- Catalog & Price Management ----------

@router.callback_query(F.data == "admin:catalog")
async def cb_admin_catalog(
    callback: CallbackQuery,
    env_cfg: EnvConfig,
    session: AsyncSession,
) -> None:
    if not is_admin(callback.from_user.id, env_cfg):
        await callback.answer("Нет доступа", show_alert=True)
        return
    catalog_repo = CatalogRepo(session)
    categories = await catalog_repo.get_categories(active_only=False)
    text = (
        "💰 <b>Управление каталогом и прайс-листом:</b>\n\n"
        "Выберите категорию для редактирования услуг и цен:"
    )
    await callback.message.edit_text(
        text, reply_markup=admin_catalog_categories_keyboard(categories)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:cat:"))
async def cb_admin_cat_services(
    callback: CallbackQuery,
    env_cfg: EnvConfig,
    session: AsyncSession,
) -> None:
    if not is_admin(callback.from_user.id, env_cfg):
        await callback.answer("Нет доступа", show_alert=True)
        return
    cat_id = callback.data.split(":", 2)[2]
    catalog_repo = CatalogRepo(session)
    category = await catalog_repo.get_category(cat_id)
    if not category:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    services = await catalog_repo.get_services(category_id=cat_id, active_only=False)
    text = (
        f"{category.emoji} <b>Услуги категории «{category.name}»:</b>\n\n"
        f"🟢 — активна, видна клиентам\n"
        f"🔴 — скрыта\n\n"
        "Нажмите на услугу для редактирования цены или добавьте новую:"
    )
    await callback.message.edit_text(
        text, reply_markup=admin_category_services_keyboard(cat_id, services)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:svc:"))
async def cb_admin_service_detail(
    callback: CallbackQuery,
    env_cfg: EnvConfig,
    session: AsyncSession,
) -> None:
    if not is_admin(callback.from_user.id, env_cfg):
        await callback.answer("Нет доступа", show_alert=True)
        return
    service_id = callback.data.split(":", 2)[2]
    catalog_repo = CatalogRepo(session)
    service = await catalog_repo.get_service(service_id)
    if not service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    status_str = "🟢 Активна (доступна для записи)" if service.is_active else "🔴 Скрыта (недоступна клиентам)"
    text = (
        f"💅 <b>Услуга: {service.name}</b>\n\n"
        f"💰 <b>Цена:</b> {service.price_min} ₽" + (f"–{service.price_max} ₽" if service.price_max else "") + "\n"
        f"⏱ <b>Длительность:</b> {service.duration_minutes} мин\n"
        f"📌 <b>Статус:</b> {status_str}\n"
    )
    if service.description:
        text += f"📝 <b>Описание:</b> {service.description}\n"

    await callback.message.edit_text(
        text, reply_markup=admin_service_manage_keyboard(service.id, service.category_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:toggle_svc:"))
async def cb_admin_toggle_service(
    callback: CallbackQuery,
    env_cfg: EnvConfig,
    session: AsyncSession,
) -> None:
    if not is_admin(callback.from_user.id, env_cfg):
        await callback.answer("Нет доступа", show_alert=True)
        return
    service_id = callback.data.split(":", 2)[2]
    catalog_repo = CatalogRepo(session)
    new_status = await catalog_repo.toggle_service_active(service_id)
    await session.commit()
    msg = "Услуга активирована" if new_status else "Услуга скрыта от клиентов"
    await callback.answer(msg, show_alert=True)
    await cb_admin_service_detail(callback, env_cfg, session)


@router.callback_query(F.data.startswith("admin:delete_svc:"))
async def cb_admin_delete_service(
    callback: CallbackQuery,
    env_cfg: EnvConfig,
    session: AsyncSession,
) -> None:
    if not is_admin(callback.from_user.id, env_cfg):
        await callback.answer("Нет доступа", show_alert=True)
        return
    service_id = callback.data.split(":", 2)[2]
    catalog_repo = CatalogRepo(session)
    service = await catalog_repo.get_service(service_id)
    if not service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return
    cat_id = service.category_id
    await catalog_repo.delete_service(service_id)
    await session.commit()
    await callback.answer("Услуга удалена", show_alert=True)

    # Return to category services
    category = await catalog_repo.get_category(cat_id)
    services = await catalog_repo.get_services(category_id=cat_id, active_only=False)
    await callback.message.edit_text(
        f"Услуги категории «{category.name}»:",
        reply_markup=admin_category_services_keyboard(cat_id, services),
    )


@router.callback_query(F.data.startswith("admin:edit_price:"))
async def cb_admin_edit_price(
    callback: CallbackQuery,
    state: FSMContext,
    env_cfg: EnvConfig,
) -> None:
    if not is_admin(callback.from_user.id, env_cfg):
        await callback.answer("Нет доступа", show_alert=True)
        return
    service_id = callback.data.split(":", 2)[2]
    await state.set_state(AdminFSM.editing_service_price)
    await state.update_data(editing_service_id=service_id)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin:catalog"))
    await callback.message.edit_text(
        "Введите <b>новую стоимость</b> услуги в рублях (целое число, например: <code>1500</code>):",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.message(AdminFSM.editing_service_price)
async def msg_admin_save_price(
    message: Message,
    state: FSMContext,
    env_cfg: EnvConfig,
    session: AsyncSession,
) -> None:
    if not is_admin(message.from_user.id, env_cfg):
        return
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Пожалуйста, введите корректное число (например: <code>1800</code>):")
        return

    new_price = int(text)
    data = await state.get_data()
    service_id = data["editing_service_id"]

    catalog_repo = CatalogRepo(session)
    await catalog_repo.update_service_price(service_id, price_min=new_price)
    await session.commit()
    await state.clear()

    service = await catalog_repo.get_service(service_id)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ К услугам категории", callback_data=f"admin:cat:{service.category_id}"))
    builder.row(InlineKeyboardButton(text="👑 В админку", callback_data="admin:menu"))

    await message.answer(
        f"✅ Цена для услуги <b>«{service.name}»</b> успешно изменена на <b>{new_price} ₽</b>!",
        reply_markup=builder.as_markup(),
    )


# ---------- Add New Service Flow ----------

@router.callback_query(F.data.startswith("admin:add_svc:"))
async def cb_admin_add_svc(
    callback: CallbackQuery,
    state: FSMContext,
    env_cfg: EnvConfig,
) -> None:
    if not is_admin(callback.from_user.id, env_cfg):
        await callback.answer("Нет доступа", show_alert=True)
        return
    cat_id = callback.data.split(":", 2)[2]
    await state.set_state(AdminFSM.adding_service_name)
    await state.update_data(new_svc_cat_id=cat_id)

    await callback.message.edit_text(
        "➕ <b>Добавление новой услуги</b>\n\n"
        "Шаг 1 из 4: Введите <b>название услуги</b> (например: <i>Smart-педикюр</i>):"
    )
    await callback.answer()


@router.message(AdminFSM.adding_service_name)
async def msg_add_svc_name(message: Message, state: FSMContext) -> None:
    await state.update_data(new_svc_name=message.text.strip())
    await state.set_state(AdminFSM.adding_service_price)
    await message.answer("Шаг 2 из 4: Введите <b>стоимость услуги</b> в рублях (например: <i>2000</i>):")


@router.message(AdminFSM.adding_service_price)
async def msg_add_svc_price(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit():
        await message.answer("❌ Введите целое число (стоимость в рублях):")
        return
    await state.update_data(new_svc_price=int(message.text.strip()))
    await state.set_state(AdminFSM.adding_service_duration)
    await message.answer(
        "Шаг 3 из 4: Введите <b>длительность выполнения в минутах</b> (например: <i>60</i> или <i>90</i>):"
    )


@router.message(AdminFSM.adding_service_duration)
async def msg_add_svc_duration(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit():
        await message.answer("❌ Введите число минут (например: 60):")
        return
    await state.update_data(new_svc_duration=int(message.text.strip()))
    await state.set_state(AdminFSM.adding_service_description)
    await message.answer(
        "Шаг 4 из 4: Введите <b>краткое описание</b> услуги (или отправьте <code>-</code>, если описание не нужно):"
    )


@router.message(AdminFSM.adding_service_description)
async def msg_add_svc_desc(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    desc = message.text.strip()
    if desc == "-":
        desc = ""

    data = await state.get_data()
    cat_id = data["new_svc_cat_id"]
    name = data["new_svc_name"]
    price = data["new_svc_price"]
    duration = data["new_svc_duration"]

    svc_id = f"svc_{uuid.uuid4().hex[:8]}"
    catalog_repo = CatalogRepo(session)
    await catalog_repo.create_service(
        service_id=svc_id,
        category_id=cat_id,
        name=name,
        price_min=price,
        price_max=None,
        duration_minutes=duration,
        description=desc,
    )
    await session.commit()
    await state.clear()

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ К услугам категории", callback_data=f"admin:cat:{cat_id}"))
    builder.row(InlineKeyboardButton(text="👑 В админку", callback_data="admin:menu"))

    await message.answer(
        f"🎉 <b>Услуга «{name}» успешно добавлена в прайс-лист!</b>\n"
        f"Стоимость: {price} ₽ | Длительность: {duration} мин\n"
        f"Она сразу доступна клиентам для записи.",
        reply_markup=builder.as_markup(),
    )


# ---------- Block / Unblock Day ----------

@router.callback_query(F.data == "admin:block_day")
async def cb_admin_block_day(
    callback: CallbackQuery, env_cfg: EnvConfig, state: FSMContext
) -> None:
    if not is_admin(callback.from_user.id, env_cfg):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminFSM.blocking_day)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin:menu"))
    await callback.message.edit_text(
        "🚫 <b>Блокировка даты</b>\n\n"
        "Введите дату для блокировки в формате <b>ГГГГ-ММ-ДД</b>\n"
        "Например: <code>2026-12-31</code>\n\n"
        "В этот день клиенты не смогут выбрать ни один слот времени.",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.message(AdminFSM.blocking_day)
async def msg_block_day_date(
    message: Message,
    state: FSMContext,
    env_cfg: EnvConfig,
    session: AsyncSession,
) -> None:
    if not is_admin(message.from_user.id, env_cfg):
        return
    date_str = message.text.strip()
    try:
        date.fromisoformat(date_str)
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте ГГГГ-ММ-ДД (например: <code>2026-11-15</code>)")
        return

    block_repo = BlockedSlotRepo(session)
    await block_repo.block_day(date_str, reason="Заблокировано администратором")
    await session.commit()
    await state.clear()

    await message.answer(
        f"✅ Дата <b>{date_str}</b> успешно заблокирована. Запись на этот день закрыта.",
        reply_markup=admin_menu_keyboard(),
    )


@router.callback_query(F.data == "admin:unblock_day")
async def cb_admin_unblock_day(
    callback: CallbackQuery, env_cfg: EnvConfig, state: FSMContext
) -> None:
    if not is_admin(callback.from_user.id, env_cfg):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminFSM.unblocking_day)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin:menu"))
    await callback.message.edit_text(
        "🔓 <b>Снятие блокировки даты</b>\n\n"
        "Введите дату, которую хотите разблокировать (ГГГГ-ММ-ДД):\n"
        "Например: <code>2026-12-31</code>",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.message(AdminFSM.unblocking_day)
async def msg_unblock_day_date(
    message: Message,
    state: FSMContext,
    env_cfg: EnvConfig,
    session: AsyncSession,
) -> None:
    if not is_admin(message.from_user.id, env_cfg):
        return
    date_str = message.text.strip()
    block_repo = BlockedSlotRepo(session)
    count = await block_repo.unblock_day(date_str)
    await session.commit()
    await state.clear()

    if count > 0:
        text = f"✅ Блокировка с даты <b>{date_str}</b> снята. День снова открыт для записи!"
    else:
        text = f"ℹ️ Дата <b>{date_str}</b> не была заблокирована."

    await message.answer(text, reply_markup=admin_menu_keyboard())
