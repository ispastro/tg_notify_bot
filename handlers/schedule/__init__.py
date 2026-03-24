# handlers/schedule/__init__.py
"""
Schedule management module.

This module provides comprehensive schedule creation, management, and editing
functionality for the Telegram bot.

Structure:
- states.py: FSM states for schedule flows
- helpers.py: Utility functions (timezone, user checks, save operations)
- ui.py: UI components (calendar, time picker, navigation)
- create.py: Schedule creation flow
- manage.py: Schedule listing, viewing, toggling, deletion
- edit.py: Schedule editing operations

All handlers are automatically registered when this module is imported.
"""

# Import all modules to register their handlers
from . import states
from . import helpers
from . import ui
from . import create
from . import manage
from . import edit

# Export commonly used functions for external use
from .helpers import ensure_user_exists, format_12hour, save_schedule
from .states import ScheduleStates, EditScheduleStates

__all__ = [
    'ensure_user_exists',
    'format_12hour',
    'save_schedule',
    'ScheduleStates',
    'EditScheduleStates',
]
