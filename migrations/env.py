# migrations/env.py
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

# === YOUR CONFIG & MODELS ===
from config import DATABASE_URL
from db.models import Base

# === ALEMBIC CONFIG ===
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# === SET DATABASE URL (FOR OFFLINE MODE) ===
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# === OFFLINE MODE (unchanged) ===
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

# === ASYNC ONLINE MODE (NEW) ===
def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online_async():
    connectable = create_async_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

# === MAIN ENTRY ===
if context.is_offline_mode():
    run_migrations_offline()
else:
    # THIS IS THE KEY LINE
    asyncio.run(run_migrations_online_async())