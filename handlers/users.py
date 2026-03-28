# handlers/users.py — FINAL, PRODUCTION-GRADE
from aiogram import types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from sqlalchemy import select

from loader import dp
from db.session import AsyncSessionLocal
from db.models import User, Batch
from config import SUPER_ADMIN_ID


# ──────────────────────────────────────────────────────────────
# FSM STATES
# ──────────────────────────────────────────────────────────────
class RegisterStates(StatesGroup):
    entering_full_name = State()
    choosing_gender = State()
    choosing_batch = State()


class EditProfileStates(StatesGroup):
    choosing_field = State()
    entering_new_name = State()
    choosing_new_gender = State()


# ──────────────────────────────────────────────────────────────
# BATCH CONFIG (MATCH startup.py)
# ──────────────────────────────────────────────────────────────
BATCHES = ["1st Year", "2nd Year", "3rd Year", "4th Year", "5th Year", "6th Year"]
GENDERS = ["Male", "Female"]


# ──────────────────────────────────────────────────────────────
# KEYBOARD BUILDER
# ──────────────────────────────────────────────────────────────
def create_gender_keyboard():
    """Return keyboard with gender options."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=gender)] for gender in GENDERS],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def create_batch_keyboard():
    """Return one-time keyboard with all batches."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=name)] for name in BATCHES],
        resize_keyboard=True,
        one_time_keyboard=True
    )


# ──────────────────────────────────────────────────────────────
# /start — WELCOME + BATCH SELECTION
# ──────────────────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()

        # Create user if not exists
        if not user:
            user = User(
                user_id=user_id,
                username=username,
                is_admin=(user_id == SUPER_ADMIN_ID),
                join_date=datetime.utcnow()
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # ───── ADMIN GREETING ─────
        if user.is_admin:
            greeting = "Welcome back, <b>Super Admin</b>!" if user_id == SUPER_ADMIN_ID else "Welcome back, <b>Admin</b>!"
            await message.answer(
                f"{greeting}\n\nUse /schedule to send broadcasts.",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove()
            )
            return

        # ───── REGULAR USER FLOW ─────
        if not user.full_name:
            await message.answer(
                "👋 <b>Welcome!</b>\n\nPlease enter your <b>full name</b>:",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.set_state(RegisterStates.entering_full_name)
            return

        if not user.gender:
            await message.answer(
                f"Hi {user.full_name}! Please select your gender:",
                reply_markup=create_gender_keyboard()
            )
            await state.set_state(RegisterStates.choosing_gender)
            return

        if not user.batch_id:
            await message.answer(
                f"Hi {user.full_name}! Please select your batch:",
                reply_markup=create_batch_keyboard()
            )
            await state.set_state(RegisterStates.choosing_batch)
            return

        # ───── FULLY REGISTERED USER ─────
        batch_result = await session.execute(
            select(Batch.name).where(Batch.id == user.batch_id)
        )
        batch_name = batch_result.scalar_one()

        await message.answer(
            f"Welcome back, <b>{user.full_name}</b>! 👋\n\n"
            f"📚 Batch: <b>{batch_name}</b>\n"
            f"⚧ Gender: {user.gender}\n\n"
            "• /my_profile — View your profile\n"
            "• /edit_batch — Change batch",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()


# ──────────────────────────────────────────────────────────────
# STEP 1: COLLECT FULL NAME
# ──────────────────────────────────────────────────────────────
@dp.message(RegisterStates.entering_full_name)
async def process_full_name(message: types.Message, state: FSMContext):
    full_name = message.text.strip()

    if len(full_name) < 2:
        await message.answer("Please enter a valid full name (at least 2 characters).")
        return

    if len(full_name) > 100:
        await message.answer("Name is too long. Please enter a shorter name.")
        return

    async with AsyncSessionLocal() as session:
        await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        from sqlalchemy import update
        await session.execute(
            update(User).where(User.user_id == message.from_user.id).values(full_name=full_name)
        )
        await session.commit()

    await message.answer(
        f"Great, <b>{full_name}</b>! 👍\n\nNow, please select your gender:",
        parse_mode="HTML",
        reply_markup=create_gender_keyboard()
    )
    await state.set_state(RegisterStates.choosing_gender)


# ──────────────────────────────────────────────────────────────
# STEP 2: COLLECT GENDER
# ──────────────────────────────────────────────────────────────
@dp.message(RegisterStates.choosing_gender)
async def process_gender(message: types.Message, state: FSMContext):
    gender = message.text.strip()

    if gender not in GENDERS:
        await message.answer(
            "Please select a valid option from the keyboard.",
            reply_markup=create_gender_keyboard()
        )
        return

    async with AsyncSessionLocal() as session:
        from sqlalchemy import update
        await session.execute(
            update(User).where(User.user_id == message.from_user.id).values(gender=gender)
        )
        await session.commit()

    await message.answer(
        "Perfect! ✅\n\nFinally, please select your batch:",
        reply_markup=create_batch_keyboard()
    )
    await state.set_state(RegisterStates.choosing_batch)


# ──────────────────────────────────────────────────────────────
# STEP 3: COLLECT BATCH
# ──────────────────────────────────────────────────────────────
@dp.message(Command("my_batch"))
async def cmd_my_batch(message: types.Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("Use /start first.")
            return

        if not user.batch_id:
            await message.answer(
                "You haven't selected a batch yet.\n"
                "Use /start to choose one.",
                reply_markup=ReplyKeyboardRemove()
            )
            return

        batch_result = await session.execute(
            select(Batch.name).where(Batch.id == user.batch_id)
        )
        batch_name = batch_result.scalar_one()

        await message.answer(
            f"Your current batch: <b>{batch_name}</b>\n\n"
            f"To change it, use: /edit_batch",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )


# ──────────────────────────────────────────────────────────────
# /edit_batch — CHANGE BATCH
# ──────────────────────────────────────────────────────────────
@dp.message(Command("edit_batch"))
async def cmd_edit_batch(message: types.Message, state: FSMContext):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("Use /start first.")
            return

        await message.answer(
            "Select your new batch:",
            reply_markup=create_batch_keyboard()
        )
        await state.set_state(RegisterStates.choosing_batch)


# ──────────────────────────────────────────────────────────────
# BATCH SELECTION HANDLER (REUSED FOR /start & /edit_batch)
# ──────────────────────────────────────────────────────────────
@dp.message(RegisterStates.choosing_batch)
async def process_batch_selection(message: types.Message, state: FSMContext):
    selected_name = message.text.strip()

    if selected_name not in BATCHES:
        await message.answer("Please select a valid batch from the keyboard.")
        return

    async with AsyncSessionLocal() as session:
        batch_result = await session.execute(
            select(Batch).where(Batch.name == selected_name)
        )
        batch = batch_result.scalar_one_or_none()

        if not batch:
            await message.answer("Batch not found. Try again.")
            return

        user_result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = user_result.scalar_one()

        from sqlalchemy import update
        await session.execute(
            update(User).where(User.user_id == message.from_user.id).values(batch_id=batch.id)
        )
        await session.commit()

        await message.answer(
            f"🎉 <b>Registration Complete!</b>\n\n"
            f"👤 Name: <b>{user.full_name}</b>\n"
            f"⚧ Gender: {user.gender}\n"
            f"📚 Batch: <b>{batch.name}</b>\n\n"
            "You're all set! You'll now receive notifications for your batch.",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML"
        )
        await state.clear()


# ──────────────────────────────────────────────────────────────
# /my_profile — VIEW PROFILE
# ──────────────────────────────────────────────────────────────
@dp.message(Command("my_profile"))
async def cmd_my_profile(message: types.Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("Use /start first.")
            return

        batch_name = "Not selected"
        if user.batch_id:
            batch_result = await session.execute(
                select(Batch.name).where(Batch.id == user.batch_id)
            )
            batch_name = batch_result.scalar_one()

        await message.answer(
            f"👤 <b>Your Profile</b>\n\n"
            f"📛 Name: <b>{user.full_name or 'Not set'}</b>\n"
            f"⚧ Gender: {user.gender or 'Not set'}\n"
            f"📚 Batch: <b>{batch_name}</b>\n"
            f"📅 Joined: {user.join_date.strftime('%Y-%m-%d')}\n\n"
            "• /edit_batch — Change batch",
            parse_mode="HTML"
        )


# ──────────────────────────────────────────────────────────────
# /my_batch — SHOW CURRENT BATCH
# ──────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────
# /edit_profile — EDIT NAME OR GENDER
# ──────────────────────────────────────────────────────────────
@dp.message(Command("edit_profile"))
async def cmd_edit_profile(message: types.Message, state: FSMContext):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("Use /start first.")
            return

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📛 Edit Name", callback_data="edit_name")],
            [InlineKeyboardButton(text="⚧ Edit Gender", callback_data="edit_gender")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="edit_cancel")]
        ])

        await message.answer(
            "✏️ <b>Edit Profile</b>\n\n"
            f"Current Name: <b>{user.full_name or 'Not set'}</b>\n"
            f"Current Gender: {user.gender or 'Not set'}\n\n"
            "What would you like to edit?",
            reply_markup=keyboard,
            parse_mode="HTML"
        )


# Handle edit name button
@dp.callback_query(F.data == "edit_name")
async def handle_edit_name(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📛 <b>Edit Name</b>\n\nPlease enter your new full name:",
        parse_mode="HTML"
    )
    await state.set_state(EditProfileStates.entering_new_name)
    await callback.answer()


# Handle edit gender button
@dp.callback_query(F.data == "edit_gender")
async def handle_edit_gender(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer(
        "⚧ <b>Edit Gender</b>\n\nPlease select your gender:",
        reply_markup=create_gender_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(EditProfileStates.choosing_new_gender)
    await callback.answer()


# Handle cancel button
@dp.callback_query(F.data == "edit_cancel")
async def handle_edit_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Profile edit cancelled.")
    await state.clear()
    await callback.answer()


# Process new name input
@dp.message(EditProfileStates.entering_new_name)
async def process_new_name(message: types.Message, state: FSMContext):
    new_name = message.text.strip()

    if len(new_name) < 2:
        await message.answer("Please enter a valid full name (at least 2 characters).")
        return

    if len(new_name) > 100:
        await message.answer("Name is too long. Please enter a shorter name.")
        return

    async with AsyncSessionLocal() as session:
        from sqlalchemy import update
        await session.execute(
            update(User).where(User.user_id == message.from_user.id).values(full_name=new_name)
        )
        await session.commit()

    await message.answer(
        f"✅ <b>Name Updated!</b>\n\nYour new name: <b>{new_name}</b>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()


# Process new gender selection
@dp.message(EditProfileStates.choosing_new_gender)
async def process_new_gender(message: types.Message, state: FSMContext):
    new_gender = message.text.strip()

    if new_gender not in GENDERS:
        await message.answer(
            "Please select a valid option from the keyboard.",
            reply_markup=create_gender_keyboard()
        )
        return

    async with AsyncSessionLocal() as session:
        from sqlalchemy import update
        await session.execute(
            update(User).where(User.user_id == message.from_user.id).values(gender=new_gender)
        )
        await session.commit()

    await message.answer(
        f"✅ <b>Gender Updated!</b>\n\nYour new gender: {new_gender}",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()