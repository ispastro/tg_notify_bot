import logging
from datetime import datetime
from aiogram import types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func
from loader import dp
from db.session import AsyncSessionLocal
from db.models import User


logger = logging.getLogger(__name__)

# --- Inline keyboard builder ---
def total_users_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh", callback_data="refresh_total_users")]
        ]
    )


# --- /total_users command ---
@dp.message(Command("total_users"))
async def cmd_total_users(message: types.Message):
    """Show total registered users (admin only)."""
    user_id = message.from_user.id

    try:
        async with AsyncSessionLocal() as session:
            # ensure both int and str user_id cases are handled
            result = await session.execute(
                select(User).where((User.user_id == user_id) | (User.user_id == str(user_id)))
            )
            user = result.scalar_one_or_none()

            if not user or not user.is_admin:
                await message.answer("⛔ You do not have permission to use this command.")
                return

            count_result = await session.execute(select(func.count(User.id)))
            total_users = count_result.scalar_one()

        text = (
            f"👥 Total registered users: <b>{total_users}</b>\n"
            f"🕒 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        await message.answer(text, reply_markup=total_users_keyboard(), parse_mode="HTML")

    except Exception as e:
        logger.exception("Error in /total_users handler:")
        await message.answer("⚠️ An unexpected error occurred while fetching user count.")


# --- Callback: refresh total users ---
@dp.callback_query(F.data == "refresh_total_users")
async def refresh_total_users(callback_query: types.CallbackQuery):
    """Refresh total user count dynamically (admin only)."""
    user_id = callback_query.from_user.id

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where((User.user_id == user_id) | (User.user_id == str(user_id)))
            )
            user = result.scalar_one_or_none()

            if not user or not user.is_admin:
                await callback_query.answer("⛔ You do not have permission.", show_alert=True)
                return

            count_result = await session.execute(select(func.count(User.id)))
            total_users = count_result.scalar_one()

        text = (
            f"👥 Total registered users: <b>{total_users}</b>\n"
            f"🕒 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        await callback_query.message.edit_text(
            text, reply_markup=total_users_keyboard(), parse_mode="HTML"
        )
        await callback_query.answer("✅ Updated!")

    except Exception as e:
        logger.exception("Error while refreshing total users:")
        await callback_query.answer("⚠️ Failed to refresh. Please try again.", show_alert=True)
