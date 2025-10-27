from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def add_admin_keyboard(username: str) -> InlineKeyboardMarkup:
    """
    Keyboard to confirm adding a new admin.

    Args:
        username (str): Telegram username of the user to be promoted.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅ Confirm @{username}", 
                    callback_data=f"confirm_add_admin:{username}"
                ),
                InlineKeyboardButton(
                    text="❌ Cancel", 
                    callback_data=f"cancel_add_admin:{username}"
                ),
            ]
        ]
    )
