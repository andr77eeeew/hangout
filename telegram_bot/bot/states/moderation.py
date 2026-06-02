from aiogram.fsm.state import State, StatesGroup


class ResolveReportForm(StatesGroup):
    waiting_for_resolution = State()
    waiting_for_notes = State()
    waiting_for_ban_decision = State()
    waiting_for_ban_reason = State()


class DismissReportForm(StatesGroup):
    waiting_for_resolution = State()
    waiting_for_notes = State()


class BanForm(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_reason = State()


class UnbanForm(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_reason = State()
