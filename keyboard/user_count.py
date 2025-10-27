from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def total_users_keyboard() -> InlineKeyboardMarkup:
    """Keyboard to refresh total users count."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh", callback_data="refresh_total_users")]
        ]
    )
