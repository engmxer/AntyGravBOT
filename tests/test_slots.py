"""Tests for time slot generation."""
from datetime import date, datetime, timedelta

import pytest

from bot.config.loader import CompanyConfig, Category, Master, WorkingHours
from bot.utils.slots import generate_time_slots


def make_config(**kwargs) -> CompanyConfig:
    defaults = dict(
        name="Test Studio",
        tagline="Test",
        emoji="💅",
        address="Test",
        phone="",
        instagram="",
        website="",
        maps_link="",
        working_days=["mon", "tue", "wed", "thu", "fri", "sat"],
        working_hours={"default": WorkingHours(start="10:00", end="18:00")},
        slot_duration_minutes=30,
        categories=[],
        masters=[],
        features={},
        texts={},
    )
    defaults.update(kwargs)
    return CompanyConfig(**defaults)


def test_generate_slots_no_bookings():
    cfg = make_config()
    tomorrow = date.today() + timedelta(days=1)
    slots = generate_time_slots(
        chosen_date=tomorrow,
        company_cfg=cfg,
        duration_minutes=60,
        existing_bookings=[],
        blocked_ranges=[],
    )
    assert len(slots) > 0
    assert all(s.is_available for s in slots)


def test_generate_slots_with_booking():
    cfg = make_config()
    tomorrow = date.today() + timedelta(days=1)
    booked_start = datetime.combine(tomorrow, datetime.strptime("11:00", "%H:%M").time())
    booked_end = datetime.combine(tomorrow, datetime.strptime("12:00", "%H:%M").time())
    slots = generate_time_slots(
        chosen_date=tomorrow,
        company_cfg=cfg,
        duration_minutes=60,
        existing_bookings=[(booked_start, booked_end)],
        blocked_ranges=[],
    )
    booked_slots = [s for s in slots if not s.is_available]
    assert len(booked_slots) > 0


def test_generate_slots_blocked_range():
    cfg = make_config(
        working_hours={"default": WorkingHours(start="10:00", end="18:00", break_start="13:00", break_end="14:00")}
    )
    tomorrow = date.today() + timedelta(days=1)
    slots = generate_time_slots(
        chosen_date=tomorrow,
        company_cfg=cfg,
        duration_minutes=60,
        existing_bookings=[],
        blocked_ranges=[],
    )
    # Slot at 13:00 should be unavailable due to break
    break_slots = [
        s for s in slots
        if s.start.hour == 13 and s.start.minute == 0
    ]
    if break_slots:
        assert not break_slots[0].is_available
