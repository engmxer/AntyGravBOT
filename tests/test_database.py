"""Unit tests for database repositories and models."""
from datetime import date, datetime, timedelta
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from bot.database.models import Base, BookingStatus
from bot.database.repo import ClientRepo, BookingRepo, CatalogRepo, BlockedSlotRepo


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_client_get_or_create(async_session: AsyncSession):
    repo = ClientRepo(async_session)
    client1 = await repo.get_or_create(telegram_id=12345, username="ivan", first_name="Иван")
    assert client1.id is not None
    assert client1.telegram_id == 12345

    # Second call should return the same client
    client2 = await repo.get_or_create(telegram_id=12345, username="ivan_new")
    assert client2.id == client1.id
    assert client2.username == "ivan_new"


@pytest.mark.asyncio
async def test_booking_crud_and_reschedule(async_session: AsyncSession):
    client_repo = ClientRepo(async_session)
    booking_repo = BookingRepo(async_session)

    client = await client_repo.get_or_create(telegram_id=99999, first_name="Анна")
    await client_repo.update_contact(99999, "+79990001122", "Анна Смирнова")

    start_time = datetime.now() + timedelta(days=2)
    booking = await booking_repo.create_booking(
        client_id=client.id,
        category_id="manicure",
        service_id="man_gel",
        service_name="Гель-лак",
        master_id="anna",
        master_name="Анна",
        price=1500,
        duration_minutes=90,
        starts_at=start_time,
    )
    assert booking.id is not None
    assert booking.status == BookingStatus.CONFIRMED

    # Test rescheduling
    new_time = start_time + timedelta(hours=3)
    rescheduled = await booking_repo.reschedule_booking(
        booking_id=booking.id, client_id=client.id, new_starts_at=new_time
    )
    assert rescheduled is not None
    assert rescheduled.starts_at == new_time

    # Test cancellation
    cancelled = await booking_repo.cancel_booking(booking.id, client.id)
    assert cancelled is True


@pytest.mark.asyncio
async def test_catalog_repo(async_session: AsyncSession):
    catalog_repo = CatalogRepo(async_session)
    svc = await catalog_repo.create_service(
        service_id="test_svc",
        category_id="test_cat",
        name="Тестовая услуга",
        price_min=1000,
        price_max=1500,
        duration_minutes=45,
        description="Описание услуги",
    )
    assert svc.id == "test_svc"

    # Test price update
    ok = await catalog_repo.update_service_price("test_svc", price_min=1200)
    assert ok is True
    updated = await catalog_repo.get_service("test_svc")
    assert updated.price_min == 1200

    # Test toggle
    is_active = await catalog_repo.toggle_service_active("test_svc")
    assert is_active is False


@pytest.mark.asyncio
async def test_blocked_slots(async_session: AsyncSession):
    block_repo = BlockedSlotRepo(async_session)
    target_date = date.today() + timedelta(days=5)
    date_str = target_date.strftime("%Y-%m-%d")

    await block_repo.block_day(date_str, reason="Праздник")
    blocked = await block_repo.get_blocked(target_date)
    assert len(blocked) == 1
    assert blocked[0].reason == "Праздник"

    unblocked_count = await block_repo.unblock_day(date_str)
    assert unblocked_count == 1
    after_unblock = await block_repo.get_blocked(target_date)
    assert len(after_unblock) == 0
