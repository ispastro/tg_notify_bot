from sqlalchemy import select, update, func
from db.session import AsyncSessionLocal
from db.models import User

async def get_user_by_username(username: str) -> User | None:
    # Normalize input (strip leading @ and compare case-insensitively)
    if not username:
        return None
    username = username.lstrip("@").strip()
    async with AsyncSessionLocal() as session:
        # Use lower-case comparison to avoid case mismatch
        result = await session.execute(
            select(User).where(func.lower(User.username) == username.lower())
        )
        return result.scalar_one_or_none()

async def promote_user_to_admin(user: User) -> bool:
    """Promote user to admin. Returns True if updated, False if already admin."""
    if user.is_admin:
        return False
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(User)
            .where(User.id == user.id)
            .values(is_admin=True)
        )
        await session.commit()
    return True
