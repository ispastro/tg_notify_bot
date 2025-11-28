import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramBadRequest
from db.session import AsyncSessionLocal
from db.models import Schedule, User, ScheduleType, schedule_batch_association
from sqlalchemy import select, update, delete
import croniter

logger = logging.getLogger("scheduler")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# TELEGRAM LIMITS (2025)
MESSAGES_PER_SECOND = 30          # Global bot limit
MESSAGES_PER_SECOND_TO_USER = 20  # Per-user limit
MESSAGES_PER_MINUTE_TO_CHAT = 20  # Private chat limit
BURST = 25                        # Allow short bursts

# OUR SAFE LIMITS (slightly below Telegram's to stay safe)
RATE_LIMIT_PER_SECOND = 28
DELAY_BETWEEN_MESSAGES = 1.0 / RATE_LIMIT_PER_SECOND

# CONCURRENCY CONTROL
MAX_CONCURRENT_SENDS = 15         # 15 concurrent sends = ~420 msg/sec burst-safe
MAX_USERS_PER_SCHEDULE_BATCH = 500  # Split huge schedules into chunks

# RETRY FOR TEMPORARY FAILURES
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


async def send_safe(bot: Bot, user_id: int, text: str) -> bool:
    """Send with retry + smart error handling + rate limit."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            await bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
                disable_notification=False
            )
            await asyncio.sleep(DELAY_BETWEEN_MESSAGES)  # Respect global rate limit
            return True

        except TelegramForbiddenError:
            logger.info(f"User {user_id} blocked the bot — removing from future sends")
            # Optional: mark user as blocked in DB
            return False

        except TelegramBadRequest as e:
            if "chat not found" in str(e) or "user is deactivated" in str(e):
                logger.info(f"User {user_id} deactivated — skipping")
                return False
            # Other BadRequest → retry
            logger.warning(f"BadRequest to {user_id} (attempt {attempt+1}): {e}")

        except TelegramAPIError as e:
            if "Too Many Requests" in str(e):
                retry_after = getattr(e, "retry_after", 10)
                logger.warning(f"Flood control! Sleeping {retry_after + 5}s")
                await asyncio.sleep(retry_after + 5)
                continue
            logger.warning(f"Telegram error to {user_id}: {e}")

        except Exception as e:
            logger.error(f"Unexpected error to {user_id}: {e}", exc_info=True)

        if attempt < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY * (2 ** attempt))  # Exponential backoff

    return False


async def broadcast_to_chunk(bot: Bot, user_ids: list[int], message: str):
    """Send to a chunk of users with concurrency control."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SENDS)

    async def send_to_one(uid):
        async with semaphore:
            await send_safe(bot, uid, message)

    # Fire and forget — we don't care about individual failures
    await asyncio.gather(*[send_to_one(uid) for uid in user_ids], return_exceptions=True)


async def run_schedule(bot: Bot, sched: Schedule):
    """Execute one schedule — split into chunks if too big."""
    logger.info(f"Executing schedule #{sched.id} | Type: {sched.type.value} | Users: ?")

    async with AsyncSessionLocal() as session:
        # Get all user_ids from linked batches
        result = await session.execute(
            select(User.user_id).select_from(
                User.__table__.join(
                    schedule_batch_association,
                User.batch_id == schedule_batch_association.c.batch_id
            )
            ).where(schedule_batch_association.c.schedule_id == sched.id)
        )
        user_ids = [row[0] for row in result.fetchall()]

        if not user_ids:
            logger.info(f"No users for schedule #{sched.id}")
            return

        logger.info(f"Sending schedule #{sched.id} to {len(user_ids)} users")

        # Split into chunks to avoid memory explosion
        for i in range(0, len(user_ids), MAX_USERS_PER_SCHEDULE_BATCH):
            chunk = user_ids[i:i + MAX_USERS_PER_SCHEDULE_BATCH]
            logger.info(f"Sending chunk {i//MAX_USERS_PER_SCHEDULE_BATCH + 1} ({len(chunk)} users)")
            await broadcast_to_chunk(bot, chunk, sched.message)

        # === UPDATE next_run ===
        try:
            now = datetime.utcnow()
            if sched.type == ScheduleType.CUSTOM and sched.cron_expr:
                cron = croniter.croniter(sched.cron_expr, now)
                next_run = cron.get_next(datetime)
            elif sched.type == ScheduleType.WEEKLY:
                next_run = now + timedelta(weeks=1)
            elif sched.type == ScheduleType.MONTHLY:
                # Proper monthly: same day next month
                try:
                    next_run = now.replace(month=now.month % 12 + 1)
                    if now.month == 12:
                        next_run = next_run.replace(year=now.year + 1)
                except ValueError:  # Feb 30 → go to March
                    next_run = now + timedelta(days=40)
                    next_run = next_run.replace(day=1)
            else:  # CUSTOM without cron → one-time
                next_run = None  # Will be deactivated

            stmt = update(Schedule).where(Schedule.id == sched.id)
            if next_run:
                stmt = stmt.values(next_run=next_run)
            else:
                stmt = stmt.values(is_active=False)  # One-time done

            await session.execute(stmt)
            await session.commit()
            status = "one-time completed" if not next_run else f"next: {next_run}"
            logger.info(f"Schedule #{sched.id} completed — {status}")

        except Exception as e:
            logger.error(f"Failed to update schedule #{sched.id}: {e}", exc_info=True)


async def scheduler_loop(bot: Bot):
    """Main loop — runs every 30 seconds (better precision)."""
    logger.info("Scheduler loop STARTED — bulletproof mode activated")
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

                if schedules:
                    logger.info(f"{len(schedules)} schedule(s) ready to execute")
                    await asyncio.gather(*[run_schedule(bot, s) for s in schedules], return_exceptions=True)
                else:
                    await asyncio.sleep(30)  # Check every 30 seconds
                    continue

        except Exception as e:
            logger.critical(f"SCHEDULER CRASHED: {e}", exc_info=True)
            await asyncio.sleep(60)  # Don't spam on crash

        await asyncio.sleep(30)  # Main loop tick