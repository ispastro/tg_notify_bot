# handlers/schedule/helpers.py
"""Helper functions for schedule management."""
from datetime import datetime, timedelta
from db.session import AsyncSessionLocal
from db.models import User, Schedule
from sqlalchemy import select
from config import SUPER_ADMIN_ID
import logging

logger = logging.getLogger(__name__)


def format_12hour(dt: datetime) -> str:
    """Convert UTC datetime to Ethiopia time and format as 12-hour."""
    # Add 3 hours to convert from UTC to Ethiopia time
    ethiopia_time = dt + timedelta(hours=3)
    period = "AM" if ethiopia_time.hour < 12 else "PM"
    hour = ethiopia_time.hour % 12
    hour = 12 if hour == 0 else hour
    minute = ethiopia_time.minute
    time_str = f"{hour}:{minute:02d} {period}" if minute > 0 else f"{hour}:00 {period}"
    return f"{ethiopia_time.strftime('%b %d, %Y')} at {time_str} (Ethiopia Time)"


async def ensure_user_exists(user_id: int, username: str | None = None) -> bool:
    """Check if user exists and is admin, create if doesn't exist."""
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                is_super = (user_id == SUPER_ADMIN_ID)
                new_user = User(
                    user_id=user_id,
                    username=username or "Unknown",
                    full_name="Admin",
                    is_admin=is_super,
                    join_date=datetime.utcnow()
                )
                session.add(new_user)
                await session.commit()
                logger.info(f"NEW USER CREATED: {user_id} | SuperAdmin: {is_super}")
                return True  # Admins always allowed

            return user.is_admin or (user_id == SUPER_ADMIN_ID)
        except Exception as e:
            logger.error(f"USER CHECK FAILED: {e}")
            return False


async def save_schedule(data: dict, admin_id: int) -> Schedule | None:
    """Save a new schedule to the database."""
    from db.models import schedule_batch_association
    
    async with AsyncSessionLocal() as session:
        try:
            # Validate required fields
            message_text = data.get("message_text")
            if not message_text:
                logger.error(f"Schedule save failed: message_text is missing or empty. Data: {data}")
                return None
            
            sched = Schedule(
                message=message_text,
                type=data["schedule_type"],
                next_run=data["next_run"],
                admin_id=admin_id,
                is_active=True,
            )
            session.add(sched)
            await session.flush()

            for bid in data["batches"]:
                await session.execute(
                    schedule_batch_association.insert().values(schedule_id=sched.id, batch_id=bid)
                )

            await session.commit()
            logger.info(f"Schedule #{sched.id} saved successfully")
            return sched
        except Exception as e:
            await session.rollback()
            logger.error(f"Schedule save failed: {e}")
            return None
