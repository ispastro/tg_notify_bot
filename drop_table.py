from db.session import engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import asyncio

async def drop_table():
    async with AsyncSession(engine) as session:
        await session.execute(text("DROP TABLE IF EXISTS users;"))
        await session.commit()

asyncio.run(drop_table())
