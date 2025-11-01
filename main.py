# main.py
import asyncio
from loader import bot, dp
import handlers.users
import handlers.admin
import handlers.schedule
from handlers.startup import seed_batches  # ← MUST IMPORT

async def main():
    from services.scheduler import scheduler_loop
    await seed_batches()  # ← RUNS ON STARTUP
    asyncio.create_task(scheduler_loop(bot))
    print("Bot starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())