from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker,AsyncSession



from config import DATABASE_URL



engine = create_async_engine(
    DATABASE_URL, 
    echo = False,


)

AsyncSessionLocal = async_sessionmaker ( 
    autocommit = False, 
    autoflush=False, 
    expire_on_commit=False,
    bind = engine, 
    class_=AsyncSession
    )

async def get_db():
    async with AsyncSessionLocal()  as  session:
        yield  session
