"""FSM state groups."""
from aiogram.fsm.state import State, StatesGroup


class BookingFSM(StatesGroup):
    """States for the booking flow."""
    choosing_category = State()
    choosing_service = State()
    choosing_master = State()
    choosing_date = State()
    choosing_time = State()
    confirming = State()
    entering_name = State()
    entering_phone = State()
    done = State()


class RescheduleFSM(StatesGroup):
    """States for rescheduling an existing booking."""
    choosing_date = State()
    choosing_time = State()
    confirming = State()


class PricelistFSM(StatesGroup):
    """States for browsing the price list."""
    browsing_categories = State()
    browsing_services = State()
    viewing_service_card = State()


class AdminFSM(StatesGroup):
    """States for admin actions."""
    main_menu = State()
    blocking_day = State()
    unblocking_day = State()
    viewing_bookings = State()

    # Catalog & Price management
    choosing_category_for_edit = State()
    choosing_service_for_edit = State()
    editing_service_price = State()
    
    # Adding new service
    adding_service_name = State()
    adding_service_price = State()
    adding_service_duration = State()
    adding_service_description = State()
