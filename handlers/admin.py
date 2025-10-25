

from aiogram import types 

from aiogram.filters import Command

from sqlalchemy import select, func
from loader import dp
from db.session import AsyncSessionLocal
from db.models import User



@dp.message(Command("total_users"))
async def cmd_total_users(message: types.Message):
    """Handle /total_users command to return total registered users."""
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        # Step 1: Fetch the user
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()

        # Step 2: Check admin privileges
        if not user or not user.is_admin:
            await message.answer("⛔ You do not have permission to use this command.")
            return

        # Step 3: Count total users
        count_result = await session.execute(select(func.count(User.id)))
        total_users = count_result.scalar_one()

    # Step 4: Send result
    await message.answer(f"👥 Total registered users: {total_users}")
