import asyncio
import asyncpg
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
import os
from datetime import datetime

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")

# Initialize bot and dispatcher
bot = Bot(
    token=BOT_TOKEN,

    default=DefaultBotProperties(parse_mode=ParseMode.HTML))

dp = Dispatcher()

# Database connection pool (we’ll use asyncpg)
async def create_db_pool():
    return await asyncpg.create_pool(DATABASE_URL)

# --- START COMMAND HANDLER ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "N/A"

    # Connect to DB
    pool = await create_db_pool()
    async with pool.acquire() as conn:
        # Check if user exists
        user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        if not user:
            # If new, ask for batch selection
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
                await message.answer(
                    "Welcome! 👋 Please select your batch:", reply_markup=keyboard
                )
        else:
            await message.answer("You’re already registered ✅")

    await pool.close()

# --- HANDLE BATCH SELECTION ---
@dp.message()
async def handle_batch_selection(message: types.Message):
    valid_batches = ["1st Year", "2nd Year", "3rd Year", "4th Year"]
    if message.text in valid_batches:
        pool = await create_db_pool()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET batch = $1 WHERE user_id = $2", message.text, message.from_user.id)
        await message.answer(f"Batch set to {message.text} ✅", reply_markup=types.ReplyKeyboardRemove())
        await pool.close()

# --- MAIN ENTRY POINT ---
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
