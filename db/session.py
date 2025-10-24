import ssl
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from contextlib import asynccontextmanager
from config import DATABASE_URL

ssl_context = ssl.create_default_context(cafile=None)
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# ✅ Disable statement caching (critical for Supabase PgBouncer)
# and enforce SSL for secure connections
DATABASE_URL = (
    f"{DATABASE_URL}"
    "&statement_cache_size=0"
    "&prepared_statement_cache_size=0"
)

# ✅ Create a robust async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,                 # Turn off in prod (set True for debugging)
    pool_size=10,               # Base pool connections
    max_overflow=20,            # Temporary extra connections for bursts
    pool_timeout=30,  
    pool_recycle=1800,          # Wait up to 30s if pool is full
    pool_pre_ping=True,         # Recycle dead connections automatically
    future=True,     
    connect_args={"ssl": ssl_context},  # ✅ asyncpg-compatible SSL
           # Modern SQLAlchemy behavior
)

# ✅ Create async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,     # Don't expire objects after commit
    autoflush=False,            # Prevent premature DB writes
    autocommit=False,
    class_=AsyncSession,
)

# ✅ Context manager for database sessions
@asynccontextmanager
async def get_db():
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except SQLAlchemyError as e:
        await session.rollback()
        raise e
    finally:
        await session.close()

# ✅ Optional: Easy helper for manual access (e.g., background tasks)
async def get_new_session() -> AsyncSession:
    return AsyncSessionLocal()
