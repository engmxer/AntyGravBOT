"""SQLAlchemy ORM models."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    RESCHEDULED = "rescheduled"
    NO_SHOW = "no_show"


class Category(Base):
    """Catalog category (e.g. Manicure, Pedicure)."""
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    emoji: Mapped[str] = mapped_column(String(16), default="💅")
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    services: Mapped[list[Service]] = relationship(
        "Service", back_populates="category", cascade="all, delete-orphan"
    )


class Service(Base):
    """Service item."""
    __tablename__ = "services"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    category_id: Mapped[str] = mapped_column(String(64), ForeignKey("categories.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    price_min: Mapped[int] = mapped_column(Integer, nullable=False)
    price_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    description: Mapped[str] = mapped_column(Text, default="")
    photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    category: Mapped[Category] = relationship("Category", back_populates="services")


class Master(Base):
    """Staff / Specialist."""
    __tablename__ = "masters"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    specialty: Mapped[str] = mapped_column(String(256), default="")
    photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Client(Base):
    """Customer."""
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(32))
    full_name: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    bookings: Mapped[list[Booking]] = relationship("Booking", back_populates="client")


class Booking(Base):
    """Customer appointment booking."""
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id"), nullable=False)
    category_id: Mapped[str] = mapped_column(String(64), nullable=False)
    service_id: Mapped[str] = mapped_column(String(64), nullable=False)
    service_name: Mapped[str] = mapped_column(String(256), nullable=False)
    master_id: Mapped[str | None] = mapped_column(String(64))
    master_name: Mapped[str | None] = mapped_column(String(256))
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus), default=BookingStatus.CONFIRMED, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    client: Mapped[Client] = relationship("Client", back_populates="bookings")


class BlockedSlot(Base):
    """Admin-blocked time slots (vacation, holiday, sanitary day)."""
    __tablename__ = "blocked_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    master_id: Mapped[str | None] = mapped_column(String(64))  # None = all masters
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # "YYYY-MM-DD"
    start_time: Mapped[str | None] = mapped_column(String(5))      # "HH:MM" or None = full day
    end_time: Mapped[str | None] = mapped_column(String(5))
    reason: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
