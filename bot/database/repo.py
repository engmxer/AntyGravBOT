"""Repository layer — all DB queries in one place."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Sequence

from sqlalchemy import and_, asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models import (
    BlockedSlot,
    Booking,
    BookingStatus,
    Category,
    Client,
    Master,
    Service,
)


class ClientRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> Client:
        result = await self.session.execute(
            select(Client).where(Client.telegram_id == telegram_id)
        )
        client = result.scalar_one_or_none()
        if client is None:
            client = Client(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
            self.session.add(client)
            await self.session.flush()
        else:
            # Update meta if changed
            if username and client.username != username:
                client.username = username
            if first_name and client.first_name != first_name:
                client.first_name = first_name
            if last_name and client.last_name != last_name:
                client.last_name = last_name
            await self.session.flush()
        return client

    async def update_contact(
        self, telegram_id: int, phone: str, full_name: str
    ) -> None:
        result = await self.session.execute(
            select(Client).where(Client.telegram_id == telegram_id)
        )
        client = result.scalar_one_or_none()
        if client:
            client.phone = phone
            client.full_name = full_name
            await self.session.flush()


class CatalogRepo:
    """Manages categories, services, and masters stored in the database."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_categories(self, active_only: bool = True) -> Sequence[Category]:
        conditions = []
        if active_only:
            conditions.append(Category.is_active == True)
        stmt = (
            select(Category)
            .where(*conditions)
            .order_by(Category.display_order, Category.name)
            .options(selectinload(Category.services))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_category(self, cat_id: str) -> Category | None:
        stmt = (
            select(Category)
            .where(Category.id == cat_id)
            .options(selectinload(Category.services))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_services(
        self,
        category_id: str | None = None,
        active_only: bool = True,
        sort_by: str | None = None,  # "price_asc", "price_desc", "name", None
    ) -> Sequence[Service]:
        conditions = []
        if active_only:
            conditions.append(Service.is_active == True)
        if category_id:
            conditions.append(Service.category_id == category_id)

        stmt = select(Service).where(*conditions)
        if sort_by == "price_asc":
            stmt = stmt.order_by(asc(Service.price_min))
        elif sort_by == "price_desc":
            stmt = stmt.order_by(desc(Service.price_min))
        elif sort_by == "name":
            stmt = stmt.order_by(asc(Service.name))
        else:
            stmt = stmt.order_by(Service.display_order, Service.name)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_service(self, service_id: str) -> Service | None:
        result = await self.session.execute(
            select(Service).where(Service.id == service_id)
        )
        return result.scalar_one_or_none()

    async def get_masters(self, active_only: bool = True) -> Sequence[Master]:
        conditions = []
        if active_only:
            conditions.append(Master.is_active == True)
        result = await self.session.execute(
            select(Master).where(*conditions).order_by(Master.name)
        )
        return result.scalars().all()

    async def get_master(self, master_id: str) -> Master | None:
        result = await self.session.execute(
            select(Master).where(Master.id == master_id)
        )
        return result.scalar_one_or_none()

    async def create_service(
        self,
        service_id: str,
        category_id: str,
        name: str,
        price_min: int,
        price_max: int | None,
        duration_minutes: int,
        description: str = "",
    ) -> Service:
        svc = Service(
            id=service_id,
            category_id=category_id,
            name=name,
            price_min=price_min,
            price_max=price_max,
            duration_minutes=duration_minutes,
            description=description,
            is_active=True,
        )
        self.session.add(svc)
        await self.session.flush()
        return svc

    async def update_service_price(
        self, service_id: str, price_min: int, price_max: int | None = None
    ) -> bool:
        svc = await self.get_service(service_id)
        if svc:
            svc.price_min = price_min
            svc.price_max = price_max
            await self.session.flush()
            return True
        return False

    async def toggle_service_active(self, service_id: str) -> bool | None:
        svc = await self.get_service(service_id)
        if svc:
            svc.is_active = not svc.is_active
            await self.session.flush()
            return svc.is_active
        return None

    async def delete_service(self, service_id: str) -> bool:
        svc = await self.get_service(service_id)
        if svc:
            await self.session.delete(svc)
            await self.session.flush()
            return True
        return False


class BookingRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_booking(
        self,
        client_id: int,
        category_id: str,
        service_id: str,
        service_name: str,
        master_id: str | None,
        master_name: str | None,
        price: int,
        duration_minutes: int,
        starts_at: datetime,
        notes: str | None = None,
    ) -> Booking:
        ends_at = starts_at + timedelta(minutes=duration_minutes)
        booking = Booking(
            client_id=client_id,
            category_id=category_id,
            service_id=service_id,
            service_name=service_name,
            master_id=master_id,
            master_name=master_name,
            price=price,
            duration_minutes=duration_minutes,
            starts_at=starts_at,
            ends_at=ends_at,
            status=BookingStatus.CONFIRMED,
            notes=notes,
        )
        self.session.add(booking)
        await self.session.flush()
        return booking

    async def get_booking_by_id(self, booking_id: int) -> Booking | None:
        result = await self.session.execute(
            select(Booking)
            .where(Booking.id == booking_id)
            .options(selectinload(Booking.client))
        )
        return result.scalar_one_or_none()

    async def get_bookings_for_date(
        self, target_date: date, master_id: str | None = None
    ) -> Sequence[Booking]:
        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        conditions = [
            Booking.starts_at >= day_start,
            Booking.starts_at < day_end,
            Booking.status != BookingStatus.CANCELLED,
        ]
        if master_id:
            conditions.append(Booking.master_id == master_id)
        result = await self.session.execute(
            select(Booking).where(and_(*conditions)).order_by(Booking.starts_at)
        )
        return result.scalars().all()

    async def get_client_bookings(
        self, client_id: int, only_upcoming: bool = True
    ) -> Sequence[Booking]:
        conditions = [Booking.client_id == client_id]
        if only_upcoming:
            conditions.append(Booking.starts_at >= datetime.now())
            conditions.append(Booking.status != BookingStatus.CANCELLED)
        result = await self.session.execute(
            select(Booking)
            .where(and_(*conditions))
            .order_by(Booking.starts_at)
        )
        return result.scalars().all()

    async def cancel_booking(self, booking_id: int, client_id: int | None = None) -> bool:
        conditions = [Booking.id == booking_id]
        if client_id is not None:
            conditions.append(Booking.client_id == client_id)

        result = await self.session.execute(select(Booking).where(and_(*conditions)))
        booking = result.scalar_one_or_none()
        if booking and booking.status != BookingStatus.CANCELLED:
            booking.status = BookingStatus.CANCELLED
            await self.session.flush()
            return True
        return False

    async def reschedule_booking(
        self, booking_id: int, client_id: int, new_starts_at: datetime
    ) -> Booking | None:
        result = await self.session.execute(
            select(Booking).where(
                and_(Booking.id == booking_id, Booking.client_id == client_id)
            )
        )
        booking = result.scalar_one_or_none()
        if booking and booking.status != BookingStatus.CANCELLED:
            booking.starts_at = new_starts_at
            booking.ends_at = new_starts_at + timedelta(minutes=booking.duration_minutes)
            booking.reminder_sent = False
            booking.status = BookingStatus.CONFIRMED
            await self.session.flush()
            return booking
        return None

    async def get_upcoming_for_reminder(
        self, reminder_delta: timedelta
    ) -> Sequence[Booking]:
        """Get confirmed bookings whose reminder hasn't been sent yet."""
        now = datetime.now()
        target = now + reminder_delta
        result = await self.session.execute(
            select(Booking).where(
                and_(
                    Booking.status == BookingStatus.CONFIRMED,
                    Booking.reminder_sent == False,
                    Booking.starts_at > now,
                    Booking.starts_at <= target,
                )
            )
        )
        return result.scalars().all()

    async def mark_reminder_sent(self, booking_id: int) -> None:
        result = await self.session.execute(
            select(Booking).where(Booking.id == booking_id)
        )
        booking = result.scalar_one_or_none()
        if booking:
            booking.reminder_sent = True
            await self.session.flush()

    async def get_week_bookings(self, week_start: date) -> Sequence[Booking]:
        start_dt = datetime.combine(week_start, datetime.min.time())
        end_dt = start_dt + timedelta(days=7)
        result = await self.session.execute(
            select(Booking)
            .where(
                and_(
                    Booking.starts_at >= start_dt,
                    Booking.starts_at < end_dt,
                    Booking.status != BookingStatus.CANCELLED,
                )
            )
            .order_by(Booking.starts_at)
        )
        return result.scalars().all()


class BlockedSlotRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_blocked(self, target_date: date, master_id: str | None = None) -> Sequence[BlockedSlot]:
        date_str = target_date.strftime("%Y-%m-%d")
        conditions = [BlockedSlot.date == date_str]
        if master_id:
            conditions.append(
                (BlockedSlot.master_id == master_id) | (BlockedSlot.master_id == None)
            )
        result = await self.session.execute(
            select(BlockedSlot).where(and_(*conditions))
        )
        return result.scalars().all()

    async def block_day(
        self, date_str: str, master_id: str | None = None, reason: str | None = None
    ) -> BlockedSlot:
        slot = BlockedSlot(date=date_str, master_id=master_id, reason=reason)
        self.session.add(slot)
        await self.session.flush()
        return slot

    async def unblock_day(self, date_str: str) -> int:
        result = await self.session.execute(
            select(BlockedSlot).where(BlockedSlot.date == date_str)
        )
        slots = result.scalars().all()
        for slot in slots:
            await self.session.delete(slot)
        await self.session.flush()
        return len(slots)
