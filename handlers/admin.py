from datetime import datetime
import logging
from aiogram import types, F
from aiogram.filters import Command
from loader import dp
from sqlalchemy import select, func
from db.session import AsyncSessionLocal
from db.models import User
from config import SUPER_ADMIN_ID
from keyboard.user_count import total_users_keyboard
from services.admin_services import get_user_by_username, promote_user_to_admin
from keyboard.add_admin import add_admin_keyboard
import logging


# Debug: log every incoming message to help verify updates reach handlers
@dp.message()
async def _debug_log_all_messages(message: types.Message):
    try:
        logging.getLogger(__name__).debug(
            "Incoming message: from=%s username=%s text=%s",
            message.from_user.id,
            message.from_user.username,
            (message.text[:300] if message.text else repr(message))
        )
    except Exception:
        logging.getLogger(__name__).exception("Failed to log incoming message")


# --- Step 1: /add_admin command ---
@dp.message(Command("add_admin"))
async def cmd_add_admin(message: types.Message):
    logging.info(f"Received /add_admin from {message.from_user.id}")
    user_id = message.from_user.id

    if user_id != SUPER_ADMIN_ID:
        await message.answer("⛔ You do not have permission.")
        return

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("⚠️ Usage: /add_admin <username>")
        return

    username = parts[1].lstrip("@")
    user = await get_user_by_username(username)
    if not user:
        await message.answer(f"⚠️ User @{username} not found.")
        return

    await message.answer(
        f"Do you want to promote @{username} to admin?",
        reply_markup=add_admin_keyboard(username)
    )


# --- Step 2: Confirm promotion callback ---
@dp.callback_query(F.data.startswith("confirm_add_admin:"))
async def confirm_add_admin(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    logging.info(f"confirm_add_admin callback from {user_id}, data={callback.data}")
    if user_id != SUPER_ADMIN_ID:
        await callback.answer("⛔ You do not have permission.", show_alert=True)
        return

    username = callback.data.split(":", 1)[1]
    user = await get_user_by_username(username)
    if not user:
        await callback.answer(f"⚠️ User @{username} not found.", show_alert=True)
        return

    updated = await promote_user_to_admin(user)
    if updated:
        await callback.message.edit_text(f"✅ @{username} is now an admin.")
    else:
        await callback.message.edit_text(f"ℹ️ @{username} is already an admin.")


# --- Step 3: Cancel promotion callback ---
@dp.callback_query(F.data.startswith("cancel_add_admin:"))
async def cancel_add_admin(callback: types.CallbackQuery):
    username = callback.data.split(":", 1)[1]
    logging.info(f"cancel_add_admin callback from {callback.from_user.id}, data={callback.data}")
    await callback.message.edit_text(f"❌ Admin promotion cancelled for @{username}.")
    await callback.answer()


# --- Step 4: /total_users command ---
@dp.message(Command("total_users"))
async def cmd_total_users(message: types.Message):
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.is_admin:
            await message.answer("⛔ You do not have permission to use this command.")
            return

        count_result = await session.execute(select(func.count(User.id)))
        total_users = count_result.scalar_one()

    await message.answer(
        f"👥 Total registered users: {total_users}\n🕒 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        reply_markup=total_users_keyboard()
    )


# --- Step 5: Refresh user count callback ---
@dp.callback_query(F.data == "refresh_total_users")
async def refresh_total_users(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    logging.info(f"refresh_total_users callback from {user_id}")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.is_admin:
            await callback_query.answer("⛔ You do not have permission.", show_alert=True)
            return

        count_result = await session.execute(select(func.count(User.id)))
        total_users = count_result.scalar_one()

    await callback_query.message.edit_text(
        f"👥 Total registered users: {total_users}\n🕒 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        reply_markup=total_users_keyboard()
    )
    await callback_query.answer("🔄 Updated!")


# --- Diagnostic: whoami (debug only) ---
@dp.message(Command("whoami"))
async def cmd_whoami(message: types.Message):
    """Return diagnostic info to help debug why admin commands may not trigger."""
    user_id = message.from_user.id
    username = message.from_user.username
    logging.info(f"whoami invoked by {user_id} (@{username})")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()

    in_db = bool(user)
    is_admin = getattr(user, 'is_admin', False) if user else False

    await message.answer(
        f"Your ID: {user_id}\nUsername: @{username}\nSUPER_ADMIN_ID (env): {SUPER_ADMIN_ID}\nIn DB: {in_db}\nis_admin: {is_admin}"
    )
