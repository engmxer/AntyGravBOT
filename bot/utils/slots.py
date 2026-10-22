"""Time slot generation utility."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from bot.config.loader import CompanyConfig
from bot.config.schemas import TimeSlot

WEEKDAY_MAP = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}


def generate_time_slots(
    chosen_date: date,
    company_cfg: CompanyConfig,
    duration_minutes: int,
    existing_bookings: list[tuple[datetime, datetime]],
    blocked_ranges: list[tuple[str | None, str | None]],
) -> list[TimeSlot]:
    """Generate available time slots for a given date.

    Args:
        chosen_date: The date to generate slots for.
        company_cfg: Company configuration with working hours and slot duration.
        duration_minutes: Duration of the requested service in minutes.
        existing_bookings: List of (start, end) datetime pairs for existing bookings.
        blocked_ranges: List of (start_time_str, end_time_str) for blocked time ranges.

    Returns:
        List of TimeSlot objects (available and unavailable).
    """
    day_key = WEEKDAY_MAP[chosen_date.weekday()]
    hours = company_cfg.working_hours.get(day_key) or company_cfg.working_hours.get("default")
    if not hours:
        return []

    def to_dt(time_str: str) -> datetime:
        h, m = map(int, time_str.split(":"))
        return datetime.combine(chosen_date, time(h, m))

    work_start = to_dt(hours.start)
    work_end = to_dt(hours.end)

    # Build blocked ranges list
    blocked: list[tuple[datetime, datetime]] = []

    # Add break
    if hours.break_start and hours.break_end:
        blocked.append((to_dt(hours.break_start), to_dt(hours.break_end)))

    # Add custom blocked ranges
    for bs, be in blocked_ranges:
        if bs and be:
            blocked.append((to_dt(bs), to_dt(be)))

    slot_duration = timedelta(minutes=company_cfg.slot_duration_minutes)
    service_duration = timedelta(minutes=duration_minutes)
    now = datetime.now()
    slots = []
    current = work_start

    while current + service_duration <= work_end:
        slot_end = current + service_duration

        # Skip slots too close in the past (1-hour buffer for same-day)
        if current < now + timedelta(hours=1):
            current += slot_duration
            continue

        # Check blocked ranges
        is_blocked = any(current < be and slot_end > bs for bs, be in blocked)

        # Check existing bookings overlap
        is_booked = any(
            current < bk_end and slot_end > bk_start
            for bk_start, bk_end in existing_bookings
        )

        slots.append(TimeSlot(
            start=current,
            end=slot_end,
            is_available=not is_blocked and not is_booked,
        ))
        current += slot_duration

    return slots
