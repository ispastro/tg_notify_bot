from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def remove_admin_keyboard(username: str) -> InlineKeyboardMarkup:
    """
    Keyboard to confirm removing an admin.

    Args:
        username (str): Telegram username of the user to be demoted.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅ Remove @{username}", 
                    callback_data=f"confirm_remove_admin:{username}"
                ),
                InlineKeyboardButton(
                    text="❌ Cancel", 
                    callback_data=f"cancel_remove_admin:{username}"
                ),
            ]
        ]
    )
