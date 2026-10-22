"""Initial database seed from CompanyConfig (YAML)."""
from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.loader import CompanyConfig
from bot.database.models import Category, Master, Service

logger = logging.getLogger(__name__)


async def seed_database_from_config(session: AsyncSession, config: CompanyConfig) -> None:
    """Populate database from YAML config if tables are empty."""
    res = await session.execute(select(Category))
    existing_categories = res.scalars().all()

    if not existing_categories:
        logger.info("Empty database detected. Seeding categories and services from YAML config...")
        for cat_order, cat_data in enumerate(config.categories):
            cat = Category(
                id=cat_data.id,
                name=cat_data.name,
                emoji=cat_data.emoji or "💅",
                display_order=cat_order,
                is_active=True,
            )
            session.add(cat)
            await session.flush()

            for svc_order, svc_data in enumerate(cat_data.services):
                svc = Service(
                    id=svc_data.id,
                    category_id=cat.id,
                    name=svc_data.name,
                    price_min=svc_data.price_min,
                    price_max=svc_data.price_max,
                    duration_minutes=svc_data.duration_minutes,
                    description=svc_data.description or "",
                    photo_url=svc_data.photo_url,
                    is_active=svc_data.enabled,
                    display_order=svc_order,
                )
                session.add(svc)

        # Seed masters
        for master_data in config.masters:
            master = Master(
                id=master_data.id,
                name=master_data.name,
                specialty=master_data.specialty or "",
                photo_url=master_data.photo_url,
                is_active=master_data.enabled,
            )
            session.add(master)

        await session.commit()
        logger.info("Database successfully seeded from config!")
