"""Configuration loader — reads ENV vars and company YAML config."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class WorkingHours:
    start: str  # "09:00"
    end: str    # "20:00"
    break_start: str | None = None
    break_end: str | None = None


@dataclass
class ServiceItem:
    id: str
    name: str
    price_min: int
    price_max: int | None
    duration_minutes: int
    description: str = ""
    photo_url: str | None = None
    enabled: bool = True


@dataclass
class Category:
    id: str
    name: str
    emoji: str
    services: list[ServiceItem] = field(default_factory=list)


@dataclass
class Master:
    id: str
    name: str
    specialty: str = ""
    photo_url: str | None = None
    enabled: bool = True


@dataclass
class CompanyConfig:
    # Identity
    name: str
    tagline: str
    emoji: str

    # Contact
    address: str
    phone: str
    instagram: str
    website: str
    maps_link: str

    # Working schedule
    working_days: list[str]      # ["mon","tue","wed","thu","fri","sat"]
    working_hours: dict[str, WorkingHours]  # per day or "default"
    slot_duration_minutes: int   # 30

    # Catalog
    categories: list[Category]
    masters: list[Master]

    # Feature flags
    features: dict[str, bool] = field(default_factory=dict)

    # Texts
    texts: dict[str, str] = field(default_factory=dict)

    def get_text(self, key: str, **kwargs: Any) -> str:
        """Return localized text with optional format args."""
        template = self.texts.get(key, key)
        return template.format(**kwargs) if kwargs else template

    def is_feature_enabled(self, feature: str) -> bool:
        return self.features.get(feature, True)

    def get_category(self, cat_id: str) -> Category | None:
        return next((c for c in self.categories if c.id == cat_id), None)

    def get_service(self, service_id: str) -> ServiceItem | None:
        for cat in self.categories:
            for svc in cat.services:
                if svc.id == service_id:
                    return svc
        return None

    def get_master(self, master_id: str) -> Master | None:
        return next((m for m in self.masters if m.id == master_id), None)

    def price_display(self, service: ServiceItem) -> str:
        if service.price_max:
            return f"{service.price_min}–{service.price_max} ₽"
        return f"{service.price_min} ₽"


@dataclass
class EnvConfig:
    bot_token: str
    company_config: str
    database_url: str
    admin_ids: list[int]
    notify_chat_id: int
    timezone: str
    reminder_hours: int
    log_level: str


def load_env_config() -> EnvConfig:
    """Load configuration from environment variables."""
    admin_ids_raw = os.getenv("ADMIN_IDS", "")
    admin_ids = [int(x.strip()) for x in admin_ids_raw.split(",") if x.strip()]

    return EnvConfig(
        bot_token=os.environ["BOT_TOKEN"],
        company_config=os.getenv("COMPANY_CONFIG", "configs/beauty_studio.yaml"),
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/booking.db"),
        admin_ids=admin_ids,
        notify_chat_id=int(os.getenv("NOTIFY_CHAT_ID", "0")),
        timezone=os.getenv("TZ", "Europe/Moscow"),
        reminder_hours=int(os.getenv("REMINDER_HOURS", "2")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


def _parse_working_hours(raw: dict) -> dict[str, WorkingHours]:
    result: dict[str, WorkingHours] = {}
    for day, hours in raw.items():
        result[day] = WorkingHours(
            start=hours["start"],
            end=hours["end"],
            break_start=hours.get("break_start"),
            break_end=hours.get("break_end"),
        )
    return result


def _parse_categories(raw: list[dict]) -> list[Category]:
    categories = []
    for cat_data in raw:
        services = [
            ServiceItem(
                id=svc["id"],
                name=svc["name"],
                price_min=svc["price_min"],
                price_max=svc.get("price_max"),
                duration_minutes=svc["duration_minutes"],
                description=svc.get("description", ""),
                photo_url=svc.get("photo_url"),
                enabled=svc.get("enabled", True),
            )
            for svc in cat_data.get("services", [])
        ]
        categories.append(
            Category(
                id=cat_data["id"],
                name=cat_data["name"],
                emoji=cat_data.get("emoji", ""),
                services=[s for s in services if s.enabled],
            )
        )
    return categories


def _parse_masters(raw: list[dict]) -> list[Master]:
    return [
        Master(
            id=m["id"],
            name=m["name"],
            specialty=m.get("specialty", ""),
            photo_url=m.get("photo_url"),
            enabled=m.get("enabled", True),
        )
        for m in raw
        if m.get("enabled", True)
    ]


def load_company_config(path: str) -> CompanyConfig:
    """Load and parse company configuration from YAML file."""
    config_path = Path(path)
    if not config_path.is_absolute():
        # Resolve relative to project root (where main.py is run from)
        config_path = Path.cwd() / config_path

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return CompanyConfig(
        name=data["name"],
        tagline=data.get("tagline", ""),
        emoji=data.get("emoji", "💼"),
        address=data.get("address", ""),
        phone=data.get("phone", ""),
        instagram=data.get("instagram", ""),
        website=data.get("website", ""),
        maps_link=data.get("maps_link", ""),
        working_days=data.get("working_days", ["mon","tue","wed","thu","fri","sat"]),
        working_hours=_parse_working_hours(data.get("working_hours", {"default": {"start":"09:00","end":"20:00"}})),
        slot_duration_minutes=data.get("slot_duration_minutes", 30),
        categories=_parse_categories(data.get("categories", [])),
        masters=_parse_masters(data.get("masters", [])),
        features=data.get("features", {}),
        texts=data.get("texts", {}),
    )
