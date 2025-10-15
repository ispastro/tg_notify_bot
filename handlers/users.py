from aiogram import types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from datetime import datetime
from database import create_db_pool
from config import SUPER_ADMIN_ID



from loader import dp  # we’ll define loader.py shortly

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "N/A"

    pool = await create_db_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        if not user:
            batches = ["1st Year", "2nd Year", "3rd Year", "4th Year"]
            keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=b)] for b in batches], resize_keyboard=True
            )
            await conn.execute(
                "INSERT INTO users (user_id, username, is_admin, join_date) VALUES ($1, $2, $3, $4)",
                user_id, username, user_id == SUPER_ADMIN_ID, datetime.now()
            )

            if user_id == SUPER_ADMIN_ID:
                await message.answer("Welcome, Super Admin 👑\nYou have full privileges.")
            else:
                await message.answer("Welcome! 👋 Please select your batch:", reply_markup=keyboard)
        else:
            await message.answer("You’re already registered ✅")
    await pool.close()

@dp.message()
async def handle_batch_selection(message: types.Message):
    valid_batches = ["1st Year", "2nd Year", "3rd Year", "4th Year"]
    if message.text in valid_batches:
        pool = await create_db_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET batch = $1 WHERE user_id = $2",
                message.text, message.from_user.id
            )
        await message.answer(
            f"Batch set to {message.text} ✅", reply_markup=ReplyKeyboardRemove()
        )
        await pool.close()
