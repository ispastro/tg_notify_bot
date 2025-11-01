# keyboard/calendar.py — CUSTOM, BULLETPROOF CALENDAR
from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import calendar

def create_calendar(year=None, month=None):
    now = datetime.now()
    year = year or now.year
    month = month or now.month

    # Header: Month + Year
    month_names = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ]
    markup = InlineKeyboardMarkup(row_width=7)
    
    # Month + Year
    markup.row(
        InlineKeyboardButton("<<", callback_data=f"calendar_prev_y_{year}_{month}"),
        InlineKeyboardButton(f"{month_names[month-1]} {year}", callback_data="ignore"),
        InlineKeyboardButton(">>", callback_data=f"calendar_next_y_{year}_{month}")
    )

    # Week days
    week_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    markup.row(*[InlineKeyboardButton(day, callback_data="ignore") for day in week_days])

    # Days
    month_calendar = calendar.monthcalendar(year, month)
    for week in month_calendar:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                today = datetime(year, month, day)
                text = f"*{day}" if today.date() == now.date() else str(day)
                row.append(InlineKeyboardButton(text, callback_data=f"calendar_day_{year}_{month}_{day}"))
        markup.row(*row)

    return markup