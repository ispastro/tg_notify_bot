# db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config import DATABASE_URL
import logging

logger = logging.getLogger(__name__)

# ENGINE: Auto-reconnect + health check
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,           # ← Checks if connection is alive
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,            # ← Reset connections every hour
    connect_args={
        "timeout": 10,
        "server_settings": {"jit": "off"}  # Optional: faster queries
    }
)

# SESSION: Thread-safe, auto-reconnect
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Generator for dependency injection (FastAPI-style)
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()