from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql import text
from db.models import Base
from config import DATABASE_URL

async def init_db():
    engine = create_async_engine(
        DATABASE_URL,
        echo=True,
        connect_args={"statement_cache_size": 0}
    )
    async with engine.begin() as conn:
        await conn.execute(text("DROP TYPE IF EXISTS scheduletype CASCADE"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

import asyncio
asyncio.run(init_db())