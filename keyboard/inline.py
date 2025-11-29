# keyboard/inline.py
from aiogram import types
from db.models import Batch

def get_batch_keyboard(batches: list[Batch], selected: list[int] | None = None):
    selected = selected or []
    buttons = []
    for b in batches:
        prefix = "Selected" if b.id in selected else " Select"
        buttons.append([
            types.InlineKeyboardButton(
                text=f"{prefix} {b.name}",
                callback_data=f"batch_{b.id}"
            )
        ])
    buttons.append([
        types.InlineKeyboardButton(text="Done", callback_data="done_batches")
    ])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

def get_schedule_type_keyboard():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Weekly", callback_data="type_weekly")],
        [types.InlineKeyboardButton(text="Monthly", callback_data="type_monthly")],
        [types.InlineKeyboardButton(text="Custom (cron)", callback_data="type_custom")],
    ])