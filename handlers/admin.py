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
from services.admin_services import get_user_by_username, promote_user_to_admin, demote_admin
from keyboard.add_admin import add_admin_keyboard
from keyboard.remove_admin import remove_admin_keyboard
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

print("handlers.admin loaded")

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# FSM STATES FOR ADMIN MANAGEMENT
# ──────────────────────────────────────────────────────────────
class AdminStates(StatesGroup):
    entering_username_to_add = State()
    entering_username_to_remove = State()

# --- SAFE: Log only NON-COMMANDS (FIXED!) ---
# Only log when user has NO active FSM state
@dp.message(~F.text.startswith("/"), StateFilter(None))
async def _log_non_commands(message: types.Message):
    logger.debug(
        "Non-command: from=%s username=%s text=%s",
        message.from_user.id,
        message.from_user.username,
        (message.text[:100] if message.text else "no text")
    )

@dp.message(Command("add_admin"))
async def cmd_add_admin(message: types.Message, state: FSMContext):
    logger.info("Received /add_admin from %s", message.from_user.id)
    user_id = message.from_user.id

    if user_id != SUPER_ADMIN_ID:
        await message.answer("You do not have permission.", parse_mode="HTML")
        return

    await message.answer(
        "👤 <b>Add Admin</b>\n\nPlease enter the username (without @):",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.entering_username_to_add)


# ──────────────────────────────────────────────────────────────
# PROCESS USERNAME INPUT FOR ADD ADMIN
# ──────────────────────────────────────────────────────────────
@dp.message(AdminStates.entering_username_to_add)
async def process_add_admin_username(message: types.Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    
    if not username:
        await message.answer("Please enter a valid username.")
        return

    user = await get_user_by_username(username)
    if not user:
        await message.answer(f"User @{username} not found.")
        await state.clear()
        return

    await message.answer(
        f"Do you want to promote <b>@{username}</b> to admin?",
        reply_markup=add_admin_keyboard(username),
        parse_mode="HTML"
    )
    await state.clear()


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
        # Update admin commands for the newly promoted user
        from utils.set_bot_commands import set_admin_commands
        from loader import bot
        from aiogram.types import BotCommandScopeChat
        
        admin_commands = [
            types.BotCommand(command="start", description="🚀 Restart"),
            types.BotCommand(command="schedule", description="📅 Create Schedule"),
            types.BotCommand(command="manage_schedules", description="⚙️ Manage Schedules"),
            types.BotCommand(command="list_schedules", description="📋 List All Schedules"),
            types.BotCommand(command="total_users", description="📊 View Stats"),
            types.BotCommand(command="whoami", description="🧑💼 View profile"),
        ]
        
        try:
            await bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=user.user_id)
            )
            logger.info(f"Admin commands set for newly promoted user {user.user_id}")
        except Exception as e:
            logger.warning(f"Could not set commands for {user.user_id}: {e}")
        
        # Notify the promoted user
        try:
            await bot.send_message(
                chat_id=user.user_id,
                text=(
                    "🎉 <b>Congratulations!</b>\n\n"
                    "You have been promoted to <b>Admin</b>.\n\n"
                    "You now have access to:\n"
                    "• 📅 Create schedules\n"
                    "• ⚙️ Manage schedules\n"
                    "• 📊 View user statistics\n\n"
                    "Use /start to see your new commands."
                ),
                parse_mode="HTML"
            )
            logger.info(f"Promotion notification sent to {user.user_id}")
        except Exception as e:
            logger.warning(f"Could not notify user {user.user_id}: {e}")
        
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

    # Format time in user-friendly way for Ethiopians
    now = datetime.now()
    time_str = now.strftime('%I:%M %p')  # 2:37 PM format
    date_str = now.strftime('%b %d, %Y')  # Mar 28, 2026 format

    await message.answer(
        f"Total registered users: {total_users}\nUpdated: {time_str} on {date_str}",
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

    # Format time in user-friendly way for Ethiopians
    now = datetime.now()
    time_str = now.strftime('%I:%M %p')  # 2:37 PM format
    date_str = now.strftime('%b %d, %Y')  # Mar 28, 2026 format

    await callback_query.message.edit_text(
        f"Total registered users: {total_users}\nUpdated: {time_str} on {date_str}",
        reply_markup=total_users_keyboard()
    )
    await callback_query.answer("Updated!")


@dp.message(Command("whoami"))
async def cmd_whoami(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Not set"
    logger.info("whoami invoked by %s (@%s)", user_id, username)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()

    if not user:
        await message.answer(
            "👤 <b>Profile</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📛 Username: @{username}\n\n"
            "Use /start to register.",
            parse_mode="HTML"
        )
        return

    await message.answer(
        "👤 <b>Your Profile</b>\n\n"
        f"📛 Name: <b>{user.full_name or 'Not set'}</b>\n"
        f"🔖 Username: @{username}\n"
        f"⚧ Gender: {user.gender or 'Not set'}",
        parse_mode="HTML"
    )


# --- /remove_admin command ---
@dp.message(Command("remove_admin"))
async def cmd_remove_admin(message: types.Message, state: FSMContext):
    logger.info("Received /remove_admin from %s", message.from_user.id)
    user_id = message.from_user.id

    if user_id != SUPER_ADMIN_ID:
        await message.answer("You do not have permission.", parse_mode="HTML")
        return

    await message.answer(
        "👤 <b>Remove Admin</b>\n\nPlease enter the username (without @):",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.entering_username_to_remove)


# ──────────────────────────────────────────────────────────────
# PROCESS USERNAME INPUT FOR REMOVE ADMIN
# ──────────────────────────────────────────────────────────────
@dp.message(AdminStates.entering_username_to_remove)
async def process_remove_admin_username(message: types.Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    
    if not username:
        await message.answer("Please enter a valid username.")
        return

    user = await get_user_by_username(username)
    if not user:
        await message.answer(f"User @{username} not found.")
        await state.clear()
        return

    if not user.is_admin:
        await message.answer(f"User @{username} is not an admin.")
        await state.clear()
        return

    await message.answer(
        f"⚠️ Are you sure you want to <b>REMOVE admin privileges</b> from <b>@{username}</b>?",
        reply_markup=remove_admin_keyboard(username),
        parse_mode="HTML"
    )
    await state.clear()


# --- Confirm removal ---
@dp.callback_query(F.data.startswith("confirm_remove_admin:"))
async def confirm_remove_admin(callback: types.CallbackQuery):
    logger.info("confirm_remove_admin from %s data=%s", callback.from_user.id, callback.data)

    if callback.from_user.id != SUPER_ADMIN_ID:
        await callback.answer("You do not have permission.", show_alert=True)
        return

    username = callback.data.split(":", 1)[1]
    user = await get_user_by_username(username)
    if not user:
        await callback.answer(f"User @{username} not found.", show_alert=True)
        return

    updated = await demote_admin(user)
    if updated:
        # Revert to default user commands
        from loader import bot
        from aiogram.types import BotCommandScopeChat
        
        default_commands = [
            types.BotCommand(command="start", description="🚀 Restart"),
            types.BotCommand(command="my_batch", description="🗂️ View batch"),
            types.BotCommand(command="edit_batch", description="🛠️ Change batch"),
            types.BotCommand(command="whoami", description="🧑💼 View profile"),
        ]
        
        try:
            await bot.set_my_commands(
                default_commands,
                scope=BotCommandScopeChat(chat_id=user.user_id)
            )
            logger.info(f"Default commands set for demoted user {user.user_id}")
        except Exception as e:
            logger.warning(f"Could not set commands for {user.user_id}: {e}")
        
        # Notify the demoted user
        try:
            await bot.send_message(
                chat_id=user.user_id,
                text=(
                    "🔔 <b>Admin Status Update</b>\n\n"
                    "Your admin privileges have been removed.\n\n"
                    "You now have regular user access."
                ),
                parse_mode="HTML"
            )
            logger.info(f"Demotion notification sent to {user.user_id}")
        except Exception as e:
            logger.warning(f"Could not notify user {user.user_id}: {e}")
        
        await callback.message.edit_text(f"✅ Admin privileges removed from @{username}.")
    else:
        await callback.message.edit_text(f"@{username} is not an admin.")
    await callback.answer()


# --- Cancel removal ---
@dp.callback_query(F.data.startswith("cancel_remove_admin:"))
async def cancel_remove_admin(callback: types.CallbackQuery):
    username = callback.data.split(":", 1)[1]
    await callback.message.edit_text(f"Action cancelled. @{username} remains an admin.")
    await callback.answer()
