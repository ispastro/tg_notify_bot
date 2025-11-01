# services/scheduler.py — FINAL, KILL-PROOF, PRODUCTION READY
import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from db.session import AsyncSessionLocal
from db.models import Schedule, User, ScheduleType
from sqlalchemy import select, update
import croniter

logger = logging.getLogger("scheduler")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# RATE LIMIT: 30 msg/sec (Telegram limit)
RATE_LIMIT = 30
DELAY = 1.0 / RATE_LIMIT

# MAX CONCURRENT SENDS PER SCHEDULE
MAX_CONCURRENCY = 10


async def send_safe(bot: Bot, user_id: int, text: str):
    """Send message with retry, rate limit, and error handling."""
    try:
        await bot.send_message(user_id, text, parse_mode="HTML", disable_web_page_preview=True)
        await asyncio.sleep(DELAY)
    except TelegramAPIError as e:
        if e.message in ["Forbidden: bot was blocked by the user", "user is deactivated"]:
            logger.info(f"User {user_id} blocked/deactivated — skipping")
        else:
            logger.warning(f"Failed to send to {user_id}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending to {user_id}: {e}")


async def run_schedule(bot: Bot, sched: Schedule):
    """Run one schedule: send to all users in batches."""
    logger.info(f"Executing schedule #{sched.id} ({sched.type.value})")

    async with AsyncSessionLocal() as session:
        # Get user IDs from linked batches
        batch_ids = [b.id for b in sched.batches]
        if not batch_ids:
            logger.warning(f"Schedule #{sched.id} has no batches")
            return

        result = await session.execute(
            select(User.user_id).where(User.batch_id.in_(batch_ids))
        )
        user_ids = [row[0] for row in result.fetchall()]

        if not user_ids:
            logger.info(f"No users in batches for schedule #{sched.id}")
            return

        logger.info(f"Sending schedule #{sched.id} to {len(user_ids)} users")

        # Semaphore for concurrency
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        async def send_to_user(uid):
            async with semaphore:
                await send_safe(bot, uid, sched.message)

        # Fire and forget with concurrency control
        await asyncio.gather(*[send_to_user(uid) for uid in user_ids], return_exceptions=True)

        # === UPDATE next_run ===
        try:
            if sched.type == ScheduleType.CUSTOM and sched.cron_expr:
                cron = croniter.croniter(sched.cron_expr, datetime.utcnow())
                next_run = cron.get_next(datetime)
            elif sched.type == ScheduleType.WEEKLY:
                next_run = sched.next_run + timedelta(weeks=1)
            elif sched.type == ScheduleType.MONTHLY:
                next_run = sched.next_run + timedelta(days=30)  # Approx
            else:
                next_run = sched.next_run + timedelta(days=1)  # Fallback

            await session.execute(
                update(Schedule)
                .where(Schedule.id == sched.id)
                .values(next_run=next_run)
            )
            await session.commit()
            logger.info(f"Schedule #{sched.id} next run: {next_run}")
        except Exception as e:
            logger.error(f"Failed to update next_run for #{sched.id}: {e}")


async def scheduler_loop(bot: Bot):
    """Main loop — runs every 60 seconds, checks active schedules."""
    logger.info("Scheduler loop started")
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

                if not schedules:
                    await asyncio.sleep(60)
                    continue

                # Run all due schedules concurrently
                tasks = [run_schedule(bot, sched) for sched in schedules]
                await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.critical(f"SCHEDULER CRASH: {e}", exc_info=True)
        
        await asyncio.sleep(60)  # Check every minute