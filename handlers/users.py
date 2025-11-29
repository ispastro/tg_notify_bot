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
    choosing_batch = State()


# ──────────────────────────────────────────────────────────────
# BATCH CONFIG (MATCH startup.py)
# ──────────────────────────────────────────────────────────────
BATCHES = ["1st Year", "2nd Year", "3rd Year", "4th Year", "5th Year", "6th Year"]


# ──────────────────────────────────────────────────────────────
# KEYBOARD BUILDER
# ──────────────────────────────────────────────────────────────
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
    full_name = message.from_user.full_name

    async with AsyncSessionLocal() as session:
        # Check if user exists in DB
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()

        # Create user if not exists (e.g. after block/unblock)
        if not user:
            user = User(
                user_id=user_id,
                username=username,
                is_admin=(user_id == SUPER_ADMIN_ID),  # Only SUPER_ADMIN_ID gets is_admin=True
                join_date=datetime.utcnow(),
                batch_id=None
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # ───── ADMIN GREETING LOGIC ─────
        if user.is_admin:
            if user_id == SUPER_ADMIN_ID:
                greeting = "Welcome back, <b>Super Admin</b>!\nYou have full control over the bot."
            else:
                greeting = "Welcome back, <b>Admin</b>!\nYou have elevated privileges."

            await message.answer(
                f"{greeting}\n\nUse /schedule to send broadcasts.",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove()
            )
            return  # Admins skip batch selection entirely

        # ───── REGULAR USER FLOW ─────
        if not user.batch_id:
            await message.answer(
                f"Hello{', ' + full_name if full_name else ''}!\n\n"
                "Please select your batch to get started:",
                reply_markup=create_batch_keyboard()
            )
            await state.set_state(RegisterStates.choosing_batch)
            return

        # User has batch → normal welcome
        batch_result = await session.execute(
            select(Batch.name).where(Batch.id == user.batch_id)
        )
        batch_name = batch_result.scalar_one()

        await message.answer(
            f"Welcome back, {full_name}!\n"
            f"You're in batch: <b>{batch_name}</b>\n\n"
            "• /my_batch — View your batch\n"
            "• /edit_batch — Change batch",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()


# ──────────────────────────────────────────────────────────────
# /my_batch — SHOW CURRENT BATCH
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
            "Select your <b>correct</b> batch:",
            reply_markup=create_batch_keyboard(),
            parse_mode="HTML"
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
        # Get batch
        batch_result = await session.execute(
            select(Batch).where(Batch.name == selected_name)
        )
        batch = batch_result.scalar_one_or_none()

        if not batch:
            await message.answer("Batch not found. Try again.")
            return

        # Update user
        user_result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = user_result.scalar_one()

        old_batch = user.batch_id
        user.batch_id = batch.id
        await session.commit()

        action = "updated" if old_batch else "selected"
        await message.answer(
            f"Success! Your batch has been <b>{action}</b> to:\n"
            f"<b>{batch.name}</b>",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML"
        )

        await state.clear()