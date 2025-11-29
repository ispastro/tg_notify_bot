from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from db.session import AsyncSessionLocal
from db.models import User
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

async def set_default_commands(bot: Bot):
    """Set default commands for ALL users."""
    user_commands = [
        BotCommand(command="start", description="Restart / Select Batch"),
        BotCommand(command="my_batch", description="View current batch"),
        BotCommand(command="edit_batch", description="Change batch"),
        BotCommand(command="whoami", description="View profile info"),
    ]
    await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
    logger.info("Default commands set.")

async def set_admin_commands(bot: Bot):
    """Set extra commands for Admins."""
    admin_commands = [
        BotCommand(command="start", description="Restart"),
        BotCommand(command="schedule", description="📅 Create Schedule"),
        BotCommand(command="list_schedules", description="📋 Manage Schedules"),
        BotCommand(command="total_users", description="📊 View Stats"),
        BotCommand(command="add_admin", description="👮 Add Admin"),
        BotCommand(command="whoami", description="👤 Admin Info"),
    ]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.is_admin == True))
        admins = result.scalars().all()
    
    for admin in admins:
        try:
            await bot.set_my_commands(
                admin_commands, 
                scope=BotCommandScopeChat(chat_id=admin.user_id)
            )
            logger.info(f"Admin commands set for {admin.user_id}")
        except Exception as e:
            logger.warning(f"Could not set commands for admin {admin.user_id}: {e}")
