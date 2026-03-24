# handlers/users_enhanced.py — ENHANCED WITH PROFILE COLLECTION
from aiogram import types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from sqlalchemy import select, update

from loader import dp
from db.session import AsyncSessionLocal
from db.models import User, Batch
from config import SUPER_ADMIN_ID


# ──────────────────────────────────────────────────────────────
# ENHANCED FSM STATES
# ──────────────────────────────────────────────────────────────
class RegisterStates(StatesGroup):
    entering_full_name = State()
    choosing_gender = State()
    choosing_batch = State()


# ──────────────────────────────────────────────────────────────
# BATCH CONFIG
# ──────────────────────────────────────────────────────────────
BATCHES = ["1st Year", "2nd Year", "3rd Year", "4th Year", "5th Year", "6th Year"]
GENDERS = ["Male", "Female", "Other"]


# ──────────────────────────────────────────────────────────────
# KEYBOARD BUILDERS
# ──────────────────────────────────────────────────────────────
def create_gender_keyboard():
    """Return keyboard with gender options."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=gender)] for gender in GENDERS],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def create_batch_keyboard():
    """Return keyboard with all batches."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=name)] for name in BATCHES],
        resize_keyboard=True,
        one_time_keyboard=True
    )


# ──────────────────────────────────────────────────────────────
# /start — ENHANCED ONBOARDING FLOW
# ──────────────────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()

        # ───── NEW USER: START ONBOARDING ─────
        if not user:
            # Create user record
            user = User(
                user_id=user_id,
                username=username,
                is_admin=(user_id == SUPER_ADMIN_ID),
                join_date=datetime.utcnow()
            )
            session.add(user)
            await session.commit()

            # Start onboarding flow
            await message.answer(
                "👋 <b>Welcome to GIBI Scheduler Bot!</b>\n\n"
                "Let's get you set up. First, please enter your <b>full name</b>:",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.set_state(RegisterStates.entering_full_name)
            return

        # ───── ADMIN GREETING ─────
        if user.is_admin:
            greeting = "Welcome back, <b>Super Admin</b>!" if user_id == SUPER_ADMIN_ID else "Welcome back, <b>Admin</b>!"
            await message.answer(
                f"{greeting}\n\nUse /schedule to send broadcasts.",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove()
            )
            return

        # ───── EXISTING USER: CHECK PROFILE COMPLETION ─────
        if not user.full_name:
            await message.answer(
                "👋 Welcome back! Let's complete your profile.\n\n"
                "Please enter your <b>full name</b>:",
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
            f"👤 Gender: {user.gender}\n\n"
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

    # Validation
    if len(full_name) < 2:
        await message.answer("Please enter a valid full name (at least 2 characters).")
        return

    if len(full_name) > 100:
        await message.answer("Name is too long. Please enter a shorter name.")
        return

    # Save to state
    await state.update_data(full_name=full_name)

    # Move to gender selection
    await message.answer(
        f"Great, <b>{full_name}</b>! 👍\n\n"
        "Now, please select your gender:",
        reply_markup=create_gender_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(RegisterStates.choosing_gender)


# ──────────────────────────────────────────────────────────────
# STEP 2: COLLECT GENDER
# ──────────────────────────────────────────────────────────────
@dp.message(RegisterStates.choosing_gender)
async def process_gender(message: types.Message, state: FSMContext):
    gender = message.text.strip()

    # Validation
    if gender not in GENDERS:
        await message.answer(
            "Please select a valid option from the keyboard.",
            reply_markup=create_gender_keyboard()
        )
        return

    # Save to state
    await state.update_data(gender=gender)

    # Move to batch selection
    await message.answer(
        "Perfect! ✅\n\n"
        "Finally, please select your batch:",
        reply_markup=create_batch_keyboard()
    )
    await state.set_state(RegisterStates.choosing_batch)


# ──────────────────────────────────────────────────────────────
# STEP 3: COLLECT BATCH & SAVE TO DATABASE
# ──────────────────────────────────────────────────────────────
@dp.message(RegisterStates.choosing_batch)
async def process_batch_selection(message: types.Message, state: FSMContext):
    selected_batch = message.text.strip()

    # Validation
    if selected_batch not in BATCHES:
        await message.answer(
            "Please select a valid batch from the keyboard.",
            reply_markup=create_batch_keyboard()
        )
        return

    # Get data from state
    data = await state.get_data()
    full_name = data.get("full_name")
    gender = data.get("gender")

    async with AsyncSessionLocal() as session:
        # Get batch
        batch_result = await session.execute(
            select(Batch).where(Batch.name == selected_batch)
        )
        batch = batch_result.scalar_one_or_none()

        if not batch:
            await message.answer("Batch not found. Please try again.")
            return

        # Update user with all collected data
        await session.execute(
            update(User)
            .where(User.user_id == message.from_user.id)
            .values(
                full_name=full_name,
                gender=gender,
                batch_id=batch.id
            )
        )
        await session.commit()

    # Success message
    await message.answer(
        f"🎉 <b>Registration Complete!</b>\n\n"
        f"👤 Name: <b>{full_name}</b>\n"
        f"⚧ Gender: {gender}\n"
        f"📚 Batch: <b>{selected_batch}</b>\n\n"
        "You're all set! You'll now receive notifications for your batch.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
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

        # Get batch name if exists
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
            "• /edit_profile — Update your profile\n"
            "• /edit_batch — Change batch",
            parse_mode="HTML"
        )


# ──────────────────────────────────────────────────────────────
# /edit_profile — EDIT PROFILE
# ──────────────────────────────────────────────────────────────
@dp.message(Command("edit_profile"))
async def cmd_edit_profile(message: types.Message, state: FSMContext):
    await message.answer(
        "Let's update your profile. Please enter your <b>full name</b>:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(RegisterStates.entering_full_name)


# ──────────────────────────────────────────────────────────────
# /edit_batch — CHANGE BATCH
# ──────────────────────────────────────────────────────────────
@dp.message(Command("edit_batch"))
async def cmd_edit_batch(message: types.Message, state: FSMContext):
    await message.answer(
        "Select your new batch:",
        reply_markup=create_batch_keyboard()
    )
    await state.set_state(RegisterStates.choosing_batch)
