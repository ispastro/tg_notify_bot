from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config import DATABASE_URL

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"statement_cache_size": 0},  # Disable prepared statement caching
    pool_size=5,  # Number of connections to keep open
    max_overflow=10,  # Allow up to 10 additional connections
    pool_timeout=30,  # Wait up to 30 seconds for a connection
    pool_recycle=1800  # Recycle connections every 30 minutes to prevent stale connections
)

AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
    class_=AsyncSession
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session