from aiogram import types
from aiogram.filters import CommandStart, Text
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime
from sqlalchemy import select

from loader import dp
from db.session import AsyncSessionLocal
from db.models import User, Batch  # Make sure Batch is imported
from config import SUPER_ADMIN_ID


BATCHES = ["1st Year", "2nd Year", "3rd Year", "4th Year"]


def create_batch_keyboard():
    """Return a ReplyKeyboardMarkup with batch options."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b)] for b in BATCHES],
        resize_keyboard=True
    )


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "N/A"

    async with AsyncSessionLocal() as session:
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
            await session.commit()  # commit here to get user.id if needed later

            if user.is_admin:
                await message.answer("Welcome, Super Admin 👑\nYou have full privileges.")
            else:
                await message.answer("Welcome! 👋 Please select your batch:", reply_markup=create_batch_keyboard())
        else:
            await message.answer("You’re already registered ✅")


@dp.message(Text(equals=BATCHES))
async def handle_batch_selection(message: types.Message):
    user_id = message.from_user.id
    batch_name = message.text

    async with AsyncSessionLocal() as session:
        # Get user and batch in one query each
        user_result = await session.execute(select(User).where(User.user_id == user_id))
        user = user_result.scalar_one_or_none()

        batch_result = await session.execute(select(Batch).where(Batch.name == batch_name))
        batch = batch_result.scalar_one_or_none()

        if user and batch:
            user.batch_id = batch.id
            await session.commit()
            await message.answer(f"✅ You’ve been assigned to {batch_name} batch!")
        else:
            await message.answer("⚠️ Something went wrong. Please try again.")
