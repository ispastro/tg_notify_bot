from aiogram import types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from datetime import datetime
from sqlalchemy import select

from loader import dp
from db.session import AsyncSessionLocal
from db.models import User, Batch
from config import SUPER_ADMIN_ID


async def get_batch_names(session):
    """Fetch all batch names from DB."""
    result = await session.execute(select(Batch.name))
    return [b[0] for b in result.all()]


def create_batch_keyboard(batch_names: list):
    """Return a ReplyKeyboardMarkup with batch options."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=name)] for name in batch_names],
        resize_keyboard=True
    )


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "N/A"

    async with AsyncSessionLocal() as session:
        user_result = await session.execute(select(User).where(User.user_id == user_id))
        user = user_result.scalar_one_or_none()

        if not user:
            user = User(
                user_id=user_id,
                username=username,
                is_admin=(user_id == SUPER_ADMIN_ID),
                join_date=datetime.utcnow()
            )
            session.add(user)
            await session.commit()  # get user.id

            if user.is_admin:
                await message.answer("Welcome, Super Admin 👑\nYou have full privileges.")
            else:
                batch_names = await get_batch_names(session)
                await message.answer(
                    "Welcome! 👋 Please select your batch:",
                    reply_markup=create_batch_keyboard(batch_names)
                )
        else:
            if not user.batch_id:
                batch_names = await get_batch_names(session)
                await message.answer(
                    "Welcome back! 👋 Please select your batch:",
                    reply_markup=create_batch_keyboard(batch_names)
                )
            else:
                await message.answer(f"You're already registered in batch ✅")


@dp.message(F.text)
async def handle_batch_selection(message: types.Message):
    user_id = message.from_user.id
    selected_batch_name = message.text.strip()

    async with AsyncSessionLocal() as session:
        # Validate user exists
        user_result = await session.execute(select(User).where(User.user_id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            await message.answer("⚠️ You are not registered. Please send /start first.")
            return

        # Fetch the batch
        batch_result = await session.execute(select(Batch).where(Batch.name == selected_batch_name))
        batch = batch_result.scalar_one_or_none()

        if not batch:
            await message.answer("⚠️ Invalid batch selection. Please select from the keyboard.")
            return

        if user.batch_id == batch.id:
            await message.answer(f"✅ You are already assigned to {batch.name} batch.", reply_markup=ReplyKeyboardRemove())
            return

        # Assign batch
        user.batch_id = batch.id
        await session.commit()
        await message.answer(f"✅ You’ve been assigned to {batch.name} batch!" , reply_markup=ReplyKeyboardRemove())
