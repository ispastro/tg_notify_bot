from aiogram import types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime
from sqlalchemy import select

from loader import dp
from db.session import AsyncSessionLocal
from db.models import User
from config import SUPER_ADMIN_ID


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "N/A"

    async with AsyncSessionLocal() as session:
       
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()

        if not user:
           
            user = User(
                user_id=user_id,
                username=username,
                is_admin=(user_id == SUPER_ADMIN_ID),
                join_date=datetime.utcnow(),
            )
            session.add(user)
            await session.commit()

          
            if user.is_admin:
                await message.answer("Welcome, Super Admin 👑\nYou have full privileges.")
            else:
                batches = ["1st Year", "2nd Year", "3rd Year", "4th Year"]
                keyboard = ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text=b)] for b in batches],
                    resize_keyboard=True
                )
                await message.answer("Welcome! 👋 Please select your batch:", reply_markup=keyboard)
        else:
            await message.answer("You’re already registered ✅")
