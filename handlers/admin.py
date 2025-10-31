# handlers/admin.py
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

print("handlers.admin loaded")

logger = logging.getLogger(__name__)

# --- SAFE: Log only NON-COMMANDS (FIXED!) ---
@dp.message(~F.text.startswith("/"))
async def _log_non_commands(message: types.Message):
    logger.debug(
        "Non-command: from=%s username=%s text=%s",
        message.from_user.id,
        message.from_user.username,
        (message.text[:100] if message.text else "no text")
    )


@dp.message(Command("add_admin"))
async def cmd_add_admin(message: types.Message):
    logger.info("Received /add_admin from %s", message.from_user.id)
    user_id = message.from_user.id

    if user_id != SUPER_ADMIN_ID:
        await message.answer("You do not have permission.", parse_mode="HTML")
        return

    parts = (message.text or "").strip().split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Usage: <code>/add_admin @username</code>", parse_mode="HTML")
        return

    username = parts[1].lstrip("@").strip()
    user = await get_user_by_username(username)
    if not user:
        await message.answer(f"User @{username} not found.", parse_mode="HTML")
        return

    await message.answer(
        f"Do you want to promote <b>@{username}</b> to admin?",
        reply_markup=add_admin_keyboard(username),
        parse_mode="HTML"
    )


# --- Confirm promotion ---
@dp.callback_query(F.data.startswith("confirm_add_admin:"))
async def confirm_add_admin(callback: types.CallbackQuery):
    logger.info("confirm_add_admin from %s data=%s", callback.from_user.id, callback.data)

    if callback.from_user.id != SUPER_ADMIN_ID:
        await callback.answer("You do not have permission.", show_alert=True)
        return

    username = callback.data.split(":", 1)[1]
    user = await get_user_by_username(username)
    if not user:
        await callback.answer(f"User @{username} not found.", show_alert=True)
        return

    updated = await promote_user_to_admin(user)
    if updated:
        await callback.message.edit_text(f"@{username} is now an admin.")
    else:
        await callback.message.edit_text(f"@{username} is already an admin.")
    await callback.answer()


# --- Cancel promotion ---
@dp.callback_query(F.data.startswith("cancel_add_admin:"))
async def cancel_add_admin(callback: types.CallbackQuery):
    username = callback.data.split(":", 1)[1]
    await callback.message.edit_text(f"Admin promotion cancelled for @{username}.")
    await callback.answer()


# --- /total_users command ---
@dp.message(Command("total_users"))
async def cmd_total_users(message: types.Message):
    logger.info("cmd_total_users invoked by %s", message.from_user.id)
    user_id = message.from_user.id

    # SUPER ADMIN BYPASS
    if user_id != SUPER_ADMIN_ID:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            if not user or not user.is_admin:
                await message.answer("You do not have permission to use this command.")
                return

    async with AsyncSessionLocal() as session:
        count_result = await session.execute(select(func.count(User.id)))
        total_users = count_result.scalar_one()

    await message.answer(
        f"Total registered users: {total_users}\nLast updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        reply_markup=total_users_keyboard()
    )


# --- Refresh user count ---
@dp.callback_query(F.data == "refresh_total_users")
async def refresh_total_users(callback_query: types.CallbackQuery):
    logger.info("refresh_total_users by %s", callback_query.from_user.id)
    user_id = callback_query.from_user.id

    if user_id != SUPER_ADMIN_ID:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            if not user or not user.is_admin:
                await callback_query.answer("You do not have permission.", show_alert=True)
                return

    async with AsyncSessionLocal() as session:
        count_result = await session.execute(select(func.count(User.id)))
        total_users = count_result.scalar_one()

    await callback_query.message.edit_text(
        f"Total registered users: {total_users}\nLast updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        reply_markup=total_users_keyboard()
    )
    await callback_query.answer("Updated!")


# --- /whoami (debug) ---
@dp.message(Command("whoami"))
async def cmd_whoami(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "None"
    logger.info("whoami invoked by %s (@%s)", user_id, username)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()

    in_db = bool(user)
    is_admin = user.is_admin if user else False

    await message.answer(
        f"**Your Info**\n"
        f"• ID: `{user_id}`\n"
        f"• Username: @{username}\n"
        f"• In DB: `{in_db}`\n"
        f"• is_admin: `{is_admin}`\n"
        f"• SUPER_ADMIN_ID: `{SUPER_ADMIN_ID}`",
        parse_mode="Markdown"
    )