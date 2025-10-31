# services/scheduler.py
import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from db.session import AsyncSessionLocal
from db.models import Schedule, User, ScheduleType
from sqlalchemy import select, update
import croniter

logger = logging.getLogger(__name__)

# Rate limit: 30 messages per second
RATE_LIMIT = 30
DELAY = 1.0 / RATE_LIMIT

async def send_message_safe(bot: Bot, user_id: int, text: str):
    try:
        await bot.send_message(user_id, text, parse_mode="HTML")
        await asyncio.sleep(DELAY)
    except TelegramAPIError as e:
        if "blocked" in str(e) or "not found" in str(e):
            logger.info(f"User {user_id} blocked bot or not found")
        else:
            logger.error(f"Failed to send to {user_id}: {e}")
            await asyncio.sleep(1)

async def run_schedule(bot: Bot, schedule: Schedule):
    async with AsyncSessionLocal() as session:
        # Get all users in selected batches
        batch_ids = [b.id for b in schedule.batches]
        result = await session.execute(
            select(User.user_id).where(User.batch_id.in_(batch_ids))
        )
        user_ids = [row[0] for row in result.fetchall()]

        logger.info(f"Sending schedule {schedule.id} to {len(user_ids)} users")

        # Send in parallel but rate-limited
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent

        async def send_with_sem(user_id):
            async with semaphore:
                await send_message_safe(bot, user_id, schedule.message)

        await asyncio.gather(*(send_with_sem(uid) for uid in user_ids))

        # Update next run
        if schedule.type == ScheduleType.WEEKLY:
            schedule.next_run += timedelta(weeks=1)
        elif schedule.type == ScheduleType.MONTHLY:
            schedule.next_run += timedelta(days=30)
        # Custom: croniter handles it

        await session.commit()

async def scheduler_loop(bot: Bot):
    while True:
        try:
            now = datetime.utcnow()
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Schedule).where(
                        Schedule.is_active == True,
                        Schedule.next_run <= now
                    )
                )
                schedules = result.scalars().all()

                for sched in schedules:
                    if sched.type == ScheduleType.CUSTOM and sched.cron_expr:
                        cron = croniter.croniter(sched.cron_expr, now)
                        sched.next_run = cron.get_next(datetime)
                    asyncio.create_task(run_schedule(bot, sched))

        except Exception as e:
            logger.error(f"Scheduler error: {e}")

        await asyncio.sleep(60)  # Check every minute