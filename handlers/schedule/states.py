# handlers/schedule/states.py
"""FSM States for schedule creation and editing."""
from aiogram.fsm.state import State, StatesGroup


class ScheduleStates(StatesGroup):
    """States for creating a new schedule."""
    choosing_batches = State()
    choosing_type = State()
    choosing_date = State()
    choosing_time = State()
    entering_message = State()
    confirming = State()


class EditScheduleStates(StatesGroup):
    """States for editing an existing schedule."""
    editing_message = State()
    editing_date = State()
    editing_time = State()
    editing_batches = State()
    editing_type = State()
    editing_cron = State()
