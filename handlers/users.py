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
BATCHES = ["1st Year", "2nd Year", "3rd Year", "4th Year"]


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
    username = message.from_user.username

    async with AsyncSessionLocal() as session:
        # Check if user exists
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            # Create new user
            user = User(
                user_id=user_id,
                username=username,
                is_admin=(user_id == SUPER_ADMIN_ID),
                join_date=datetime.utcnow()
            )
            session.add(user)
            await session.commit()

            if user.is_admin:
                await message.answer(
                    "Welcome, Super Admin. You have full privileges.\n\n"
                    "Use /schedule to create broadcasts.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return

        # User exists — check batch
        if not user.batch_id:
            await message.answer(
                "Welcome! Please select your batch:",
                reply_markup=create_batch_keyboard()
            )
            await state.set_state(RegisterStates.choosing_batch)
        else:
            # Already has batch
            batch_result = await session.execute(
                select(Batch.name).where(Batch.id == user.batch_id)
            )
            batch_name = batch_result.scalar_one()
            await message.answer(
                f"Welcome back!\n"
                f"You're in batch: <b>{batch_name}</b>\n\n"
                f"• /my_batch — View batch\n"
                f"• /edit_batch — Change batch",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove()
            )


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