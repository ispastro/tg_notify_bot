from db.session import AsyncSessionLocal
from db.models import Batch
from sqlalchemy import select

BATCHES = ["1st Year", "2nd Year", "3rd Year", "4th Year"]

async def seed_batches():
    """Ensure all batches exist in the DB."""
    async with AsyncSessionLocal() as session:
        for name in BATCHES:
            result = await session.execute(select(Batch).where(Batch.name == name))
            if not result.scalar_one_or_none():
                session.add(Batch(name=name))
        await session.commit()
