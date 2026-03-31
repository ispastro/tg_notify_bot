import asyncio
import logging
import time
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter
from db.session import AsyncSessionLocal
from db.models import Schedule, User, ScheduleType, schedule_batch_association
from sqlalchemy import select, update
import croniter
from utils.message_utils import personalize_message

logger = logging.getLogger("scheduler")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ==============================================================================
# CONFIGURATION
# ==============================================================================
TELEGRAM_GLOBAL_LIMIT = 30.0  # Messages per second (Global)
SAFE_GLOBAL_LIMIT = 25.0      # Our target safe limit
WORKER_COUNT = 30             # Number of concurrent workers (enough to saturate the limit)
MAX_RETRIES = 5               # Robust retry count
BASE_RETRY_DELAY = 2.0        # Initial retry delay
MAX_QUEUE_SIZE = 50000        # Safety cap for memory

# ==============================================================================
# RATE LIMITER (Token Bucket)
# ==============================================================================
class TokenBucket:
    """
    A robust token bucket rate limiter for global throughput control.
    Ensures we never exceed 'rate' actions per second across all workers.
    """
    def __init__(self, rate: float):
        self.rate = rate
        self.tokens = rate  # Start full
        self.last_update = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self):
        """Wait until a token is available, then consume it."""
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            # Refill tokens
            new_tokens = elapsed * self.rate
            if new_tokens > 0:
                self.tokens = min(self.rate, self.tokens + new_tokens)
                self.last_update = now

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return
            
            # Calculate wait time
            wait_time = (1.0 - self.tokens) / self.rate
            
            # Reserve the token (consume it effectively in the future)
            self.tokens = 0.0
            self.last_update += wait_time # Advance logical time
            
        # Wait outside the lock to allow other acquirers to queue effectively
        if wait_time > 0:
            await asyncio.sleep(wait_time)


# ==============================================================================
# BROADCAST MANAGER
# ==============================================================================
class BroadcastManager:
    """
    Manages the queueing and safe delivery of messages to thousands of users.
    Uses a worker pool pattern to handle high concurrency while respecting limits.
    """
    def __init__(self, bot: Bot):
        self.bot = bot
        self.queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        self.limiter = TokenBucket(rate=SAFE_GLOBAL_LIMIT)
        self.workers = []
        self.running = False
        self.total_enqueued = 0
        self.total_sent = 0

    def start(self):
        """Start the worker pool."""
        if self.running:
            return
        self.running = True
        self.workers = [asyncio.create_task(self._worker(i)) for i in range(WORKER_COUNT)]
        logger.info(f"BroadcastManager STARTED with {WORKER_COUNT} workers.")

    async def stop(self):
        """Gracefully stop workers (wait for queue to empty? No, hard stop for now)."""
        self.running = False
        # In a real shutdown, we might wait for join(), but for bot reload we just cancel
        for w in self.workers:
            w.cancel()
        logger.info("BroadcastManager STOPPED.")

    async def enqueue_job(self, user_id: int, message: str, sched_id: int, full_name: str = None, media_type: str = None, media_file_id: str = None):
        """Add a job to the queue. Non-blocking unless queue is full."""
        try:
            self.queue.put_nowait((user_id, message, sched_id, full_name, media_type, media_file_id))
            self.total_enqueued += 1
            if self.total_enqueued % 1000 == 0:
                logger.info(f"Queue Stats: size={self.queue.qsize()}, total_enqueued={self.total_enqueued}")
        except asyncio.QueueFull:
            logger.warning("Broadcast queue FULL! Waiting to enqueue...")
            await self.queue.put((user_id, message, sched_id, full_name, media_type, media_file_id))

    async def _worker(self, worker_id: int):
        """Worker loop processing messages from queue."""
        while self.running:
            try:
                user_id, text, sched_id, full_name, media_type, media_file_id = await self.queue.get()
                
                # Debug logging
                logger.info(f"Worker {worker_id}: user_id={user_id}, full_name={full_name}, media_type={media_type}")
                
                # Personalize caption/message if full_name provided
                if full_name and text:
                    text = personalize_message(text, full_name)
                    logger.info(f"Worker {worker_id}: Personalized message for {user_id}")
                elif full_name and not text:
                    # Media without caption - create greeting
                    text = f"ሰላም {full_name}"
                
                # Enforce Rate Limit
                await self.limiter.acquire()
                
                # Send based on media type (text is already personalized)
                if media_type:
                    success = await self._send_media(user_id, media_type, media_file_id, text)
                else:
                    success = await self._send_safe(user_id, text)
                
                if success:
                    self.total_sent += 1
                
                self.queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} crash: {e}", exc_info=True)
                await asyncio.sleep(1) # Prevent tight loop crash

    async def _send_safe(self, user_id: int, text: str) -> bool:
        """Robust send with retry logic."""
        for attempt in range(MAX_RETRIES + 1):
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                return True

            except TelegramRetryAfter as e:
                # We hit a limit despite our bucket. Respect Telegram's wish.
                wait_s = e.retry_after
                logger.warning(f"FloodWait: Sleeping {wait_s}s for user {user_id}")
                await asyncio.sleep(wait_s)
                # Retry immediately after waiting
                continue

            except TelegramForbiddenError:
                # Blocked
                return False

            except TelegramBadRequest as e:
                # Check for "chat not found"
                if "chat not found" in str(e).lower() or "deactivated" in str(e).lower():
                    return False
                logger.warning(f"BadRequest to {user_id}: {e}")
                # Don't retry bad requests typically
                return False

            except TelegramAPIError as e:
                logger.warning(f"API Error to {user_id} (Attempt {attempt+1}/{MAX_RETRIES}): {e}")

            except Exception as e:
                logger.error(f"Unexpected error to {user_id}: {e}")

            # Exponential Backoff for retries
            if attempt < MAX_RETRIES:
                sleep_time = BASE_RETRY_DELAY * (2 ** attempt)
                await asyncio.sleep(sleep_time)

        logger.error(f"Failed to send to {user_id} after {MAX_RETRIES} attempts.")
        return False

    async def _send_media(self, user_id: int, media_type: str, file_id: str, caption: str = None) -> bool:
        """Send media (photo/video/document) with caption (already personalized)."""
        for attempt in range(MAX_RETRIES + 1):
            try:
                if media_type == "photo":
                    await self.bot.send_photo(
                        chat_id=user_id,
                        photo=file_id,
                        caption=caption,
                        parse_mode="HTML"
                    )
                elif media_type == "video":
                    await self.bot.send_video(
                        chat_id=user_id,
                        video=file_id,
                        caption=caption,
                        parse_mode="HTML"
                    )
                elif media_type == "document":
                    await self.bot.send_document(
                        chat_id=user_id,
                        document=file_id,
                        caption=caption,
                        parse_mode="HTML"
                    )
                return True

            except TelegramRetryAfter as e:
                wait_s = e.retry_after
                logger.warning(f"FloodWait: Sleeping {wait_s}s for user {user_id}")
                await asyncio.sleep(wait_s)
                continue

            except TelegramForbiddenError:
                return False

            except TelegramBadRequest as e:
                if "chat not found" in str(e).lower() or "deactivated" in str(e).lower():
                    return False
                logger.warning(f"BadRequest to {user_id}: {e}")
                return False

            except TelegramAPIError as e:
                logger.warning(f"API Error to {user_id} (Attempt {attempt+1}/{MAX_RETRIES}): {e}")

            except Exception as e:
                logger.error(f"Unexpected error to {user_id}: {e}")

            if attempt < MAX_RETRIES:
                sleep_time = BASE_RETRY_DELAY * (2 ** attempt)
                await asyncio.sleep(sleep_time)

        logger.error(f"Failed to send media to {user_id} after {MAX_RETRIES} attempts.")
        return False


# ==============================================================================
# SCHEDULER LOGIC
# ==============================================================================
running_schedules = set()
broadcast_manager: BroadcastManager = None

async def execute_schedule_logic(bot: Bot, sched_id: int):
    """Fetches users and feeds the BroadcastManager."""
    logger.info(f"Processing execution for Schedule #{sched_id}")
    
    try:
        async with AsyncSessionLocal() as session:
            # 1. Fetch Schedule
            sched = await session.get(Schedule, sched_id)
            if not sched or not sched.is_active:
                logger.warning("Schedule invalid or inactive.")
                return

            # 2. Fetch Users with full_name for personalization
            stmt = select(User.user_id, User.full_name).join(
                schedule_batch_association, 
                User.batch_id == schedule_batch_association.c.batch_id
            ).where(
                schedule_batch_association.c.schedule_id == sched.id
            )
            
            result = await session.execute(stmt)
            users = result.fetchall()

            if not users:
                logger.info(f"No users found for Schedule #{sched.id}")
            else:
                logger.info(f"Enqueueing {len(users)} messages for Schedule #{sched.id}")
                # Determine what to send
                message_content = sched.caption if sched.media_type else sched.message
                
                for user_id, full_name in users:
                    logger.info(f"Enqueuing for user_id={user_id}, full_name={full_name}")
                    await broadcast_manager.enqueue_job(
                        user_id, 
                        message_content, 
                        sched.id, 
                        full_name,
                        sched.media_type,
                        sched.media_file_id
                    )

            # 3. Calculate Next Run
            now = datetime.utcnow()
            next_run = None
            
            if sched.type == ScheduleType.CUSTOM and sched.cron_expr:
                try:
                    cron = croniter.croniter(sched.cron_expr, now)
                    next_run = cron.get_next(datetime)
                except Exception as e:
                    logger.error(f"Cron error: {e}")
            elif sched.type == ScheduleType.WEEKLY:
                next_run = now + timedelta(weeks=1)
            elif sched.type == ScheduleType.MONTHLY:
                # Simple monthly logic
                next_run = now + timedelta(days=30) # Fallback
                try:
                    new_month = (now.month % 12) + 1
                    year_add = 1 if new_month == 1 else 0
                    next_run = now.replace(year=now.year + year_add, month=new_month)
                except ValueError:
                    pass

            # 4. Update DB
            values = {}
            if next_run:
                values["next_run"] = next_run
            else:
                values["is_active"] = False
            
            await session.execute(update(Schedule).where(Schedule.id == sched.id).values(**values))
            await session.commit()
            
            logger.info(f"Schedule #{sched.id} processed. Next run: {next_run}")

    except Exception as e:
        logger.error(f"Example execution failed: {e}", exc_info=True)
    finally:
        running_schedules.discard(sched_id)


async def scheduler_loop(bot: Bot):
    """Main background loop."""
    global broadcast_manager
    if broadcast_manager is None:
        broadcast_manager = BroadcastManager(bot)
        broadcast_manager.start()

    logger.info("Scheduler loop STARTED (Robust Mode)")

    while True:
        try:
            now = datetime.utcnow()
            async with AsyncSessionLocal() as session:
                # Find due schedules
                stmt = select(Schedule).where(
                    Schedule.is_active == True,
                    Schedule.next_run <= now
                )
                result = await session.execute(stmt)
                schedules = result.scalars().all()

                for sched in schedules:
                    if sched.id in running_schedules:
                        continue
                    
                    running_schedules.add(sched.id)
                    # Use create_task to run non-blocking
                    asyncio.create_task(execute_schedule_logic(bot, sched.id))

            await asyncio.sleep(10)

        except Exception as e:
            logger.critical(f"Scheduler loop crash: {e}", exc_info=True)
            await asyncio.sleep(10)