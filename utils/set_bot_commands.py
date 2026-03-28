from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from db.session import AsyncSessionLocal
from db.models import User
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

async def set_default_commands(bot: Bot):
    """Set default commands for ALL users."""
    commands = [
        BotCommand(command="start", description="🚀 Restart"),
        BotCommand(command="my_batch", description="🗂️ View batch"),
        BotCommand(command="edit_batch", description="🛠️ Change batch"),
        BotCommand(command="edit_profile", description="✏️ Edit profile"),
        BotCommand(command="whoami", description="🧑💼 View profile"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    logger.info("Default commands set.")

async def set_admin_commands(bot: Bot):
    """Set extra commands for Admins."""
    from config import SUPER_ADMIN_ID
    
    # Regular admin commands (without add/remove admin)
    admin_commands = [
        BotCommand(command="start", description="🚀 Restart"),
        BotCommand(command="schedule", description="📅 Create Schedule"),
        BotCommand(command="manage_schedules", description="⚙️ Manage Schedules"),
        BotCommand(command="list_schedules", description="📋 List All Schedules"),
        BotCommand(command="total_users", description="📊 View Stats"),
        BotCommand(command="edit_profile", description="✏️ Edit profile"),
        BotCommand(command="whoami", description="🧑💼 View profile"),
    ]
    
    # Super admin commands (with add/remove admin)
    super_admin_commands = [
        BotCommand(command="start", description="🚀 Restart"),
        BotCommand(command="schedule", description="📅 Create Schedule"),
        BotCommand(command="manage_schedules", description="⚙️ Manage Schedules"),
        BotCommand(command="list_schedules", description="📋 List All Schedules"),
        BotCommand(command="total_users", description="📊 View Stats"),
        BotCommand(command="add_admin", description="👮 Add Admin"),
        BotCommand(command="remove_admin", description="🚫 Remove Admin"),
        BotCommand(command="edit_profile", description="✏️ Edit profile"),
        BotCommand(command="whoami", description="🧑💼 View profile"),
    ]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.is_admin == True))
        admins = result.scalars().all()
    
    for admin in admins:
        try:
            # Super admin gets extra commands
            commands = super_admin_commands if admin.user_id == SUPER_ADMIN_ID else admin_commands
            await bot.set_my_commands(
                commands, 
                scope=BotCommandScopeChat(chat_id=admin.user_id)
            )
            logger.info(f"{'Super admin' if admin.user_id == SUPER_ADMIN_ID else 'Admin'} commands set for {admin.user_id}")
        except Exception as e:
            logger.warning(f"Could not set commands for admin {admin.user_id}: {e}")
