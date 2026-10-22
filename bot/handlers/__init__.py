"""Handler registration."""
from aiogram import Dispatcher

from bot.handlers.common import router as common_router
from bot.handlers.booking import router as booking_router
from bot.handlers.pricelist import router as pricelist_router
from bot.handlers.my_bookings import router as my_bookings_router
from bot.handlers.admin import router as admin_router


def register_all_handlers(dp: Dispatcher) -> None:
    dp.include_router(common_router)
    dp.include_router(booking_router)
    dp.include_router(pricelist_router)
    dp.include_router(my_bookings_router)
    dp.include_router(admin_router)
