"""Tests for company config loading."""
from pathlib import Path

import pytest

from bot.config.loader import CompanyConfig, ServiceItem, load_company_config


def test_load_beauty_config():
    config_path = Path(__file__).parent.parent / "configs" / "beauty_studio.yaml"
    if not config_path.exists():
        pytest.skip("Config file not found")
    cfg = load_company_config(str(config_path))
    assert cfg.name == "Nail Studio Bloom"
    assert len(cfg.categories) > 0
    assert len(cfg.masters) > 0
    assert cfg.slot_duration_minutes == 30


def test_price_display_no_max():
    cfg = CompanyConfig(
        name="T", tagline="T", emoji="T", address="", phone="", instagram="",
        website="", maps_link="", working_days=[], working_hours={},
        slot_duration_minutes=30, categories=[], masters=[],
    )
    svc = ServiceItem(id="x", name="x", price_min=1000, price_max=None, duration_minutes=60)
    assert cfg.price_display(svc) == "1000 ₽"


def test_price_display_with_max():
    cfg = CompanyConfig(
        name="T", tagline="T", emoji="T", address="", phone="", instagram="",
        website="", maps_link="", working_days=[], working_hours={},
        slot_duration_minutes=30, categories=[], masters=[],
    )
    svc = ServiceItem(id="x", name="x", price_min=1000, price_max=2000, duration_minutes=60)
    assert cfg.price_display(svc) == "1000–2000 ₽"
