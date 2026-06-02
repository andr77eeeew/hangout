from aiogram.fsm.state import State, StatesGroup


class ActivityForm(StatesGroup):
    waiting_for_category = State()
    waiting_for_type = State()
    waiting_for_format = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_date = State()
    waiting_for_location = State()
    waiting_for_extra_data = State()
    waiting_for_max_members = State()
    waiting_for_tags = State()
    waiting_for_confirmation = State()
