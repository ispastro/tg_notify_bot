# services/admin_services.py
from sqlalchemy import select, update, func
from db.session import AsyncSessionLocal
from db.models import User
import logging
import asyncio

logger = logging.getLogger(__name__)

async def _execute_with_retry(query_func, max_retries=3):
    """Execute DB query with retry on connection loss"""
    for attempt in range(max_retries):
        async with AsyncSessionLocal() as session:
            try:
                return await query_func(session)
            except Exception as e:
                if "connection" in str(e).lower() or "closed" in str(e).lower():
                    logger.warning(f"DB connection lost. Retry {attempt + 1}/{max_retries}: {e}")
                    if attempt == max_retries - 1:
                        logger.error("Max retries reached. Giving up.")
                        raise
                    await asyncio.sleep(1 + attempt)  # Exponential backoff
                else:
                    logger.error(f"DB error (non-recoverable): {e}")
                    raise

async def get_user_by_username(username: str) -> User | None:
    if not username:
        return None
    username = username.lstrip("@").strip()

    async def _query(session):
        result = await session.execute(
            select(User).where(func.lower(User.username) == username.lower())
        )
        return result.scalar_one_or_none()

    return await _execute_with_retry(_query)

async def promote_user_to_admin(user: User) -> bool:
    if not user or user.is_admin:
        return False

    async def _update(session):
        await session.execute(
            update(User)
            .where(User.id == user.id)
            .values(is_admin=True)
        )
        await session.commit()
        return True

    return await _execute_with_retry(_update)