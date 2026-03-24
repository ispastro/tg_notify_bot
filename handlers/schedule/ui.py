# handlers/schedule/ui.py
"""UI components for schedule management (calendar, time picker, navigation)."""
from aiogram import types, F
from datetime import datetime
import calendar
from loader import dp
from .helpers import ensure_user_exists


def create_calendar(year: int | None = None, month: int | None = None):
    """Create an interactive calendar widget."""
    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month

    inline = []
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    prev = types.InlineKeyboardButton(text="◀️ Previous", callback_data=f"cal_prev_{year}_{month}")
    nxt = types.InlineKeyboardButton(text="Next ▶️", callback_data=f"cal_next_{year}_{month}")
    title = types.InlineKeyboardButton(text=f"{month_names[month - 1]} {year}", callback_data="ignore")
    inline.append([prev, title, nxt])

    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    inline.append([types.InlineKeyboardButton(text=d, callback_data="ignore") for d in days])

    cal = calendar.monthcalendar(year, month)
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(types.InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                txt = f"*{day}" if datetime(year, month, day).date() == now.date() else str(day)
                row.append(types.InlineKeyboardButton(text=txt, callback_data=f"cal_day_{year}_{month}_{day}"))
        inline.append(row)

    return types.InlineKeyboardMarkup(inline_keyboard=inline)


def create_time_picker():
    """Create a 12-hour time picker widget."""
    inline = []
    # AM Hours
    row = []
    for h in range(12):
        hour_12 = 12 if h == 0 else h
        text = f"{hour_12}:00 AM"
        callback = f"time_{h}"
        row.append(types.InlineKeyboardButton(text=text, callback_data=callback))
        if len(row) == 3:
            inline.append(row)
            row = []
    if row:
        inline.append(row)

    # PM Hours
    row = []
    for h in range(12, 24):
        hour_12 = h - 12
        hour_12 = 12 if hour_12 == 0 else hour_12
        text = f"{hour_12}:00 PM"
        callback = f"time_{h}"
        row.append(types.InlineKeyboardButton(text=text, callback_data=callback))
        if len(row) == 3:
            inline.append(row)
            row = []
    if row:
        inline.append(row)

    return types.InlineKeyboardMarkup(inline_keyboard=inline)


# ----------------------------------------------------------------------
# CALENDAR NAVIGATION HANDLERS
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("cal_prev_"))
async def calendar_prev(callback: types.CallbackQuery):
    """Navigate to previous month."""
    parts = callback.data.split("_")
    year, month = int(parts[2]), int(parts[3])
    # Go to previous month
    if month == 1:
        year -= 1
        month = 12
    else:
        month -= 1
    await callback.message.edit_reply_markup(reply_markup=create_calendar(year, month))
    await callback.answer()


@dp.callback_query(F.data.startswith("cal_next_"))
async def calendar_next(callback: types.CallbackQuery):
    """Navigate to next month."""
    parts = callback.data.split("_")
    year, month = int(parts[2]), int(parts[3])
    # Go to next month
    if month == 12:
        year += 1
        month = 1
    else:
        month += 1
    await callback.message.edit_reply_markup(reply_markup=create_calendar(year, month))
    await callback.answer()


@dp.callback_query(F.data == "ignore")
async def ignore_callback(callback: types.CallbackQuery):
    """Ignore calendar header clicks."""
    await callback.answer()
