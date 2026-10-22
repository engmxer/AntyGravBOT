"""Pydantic-style type aliases and shared data classes."""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TimeSlot:
    start: datetime
    end: datetime
    is_available: bool = True

    @property
    def label(self) -> str:
        return self.start.strftime("%H:%M")
