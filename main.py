# main.py
import asyncio
import logging
from loader import bot, dp

# Import modules → runs decorators → registers handlers
import handlers.startup     # if seed_batches is here
import handlers.users
import handlers.admin

# OR if seed_batches is in startup.py:
# from handlers.startup import seed_batches

async def main():
    logging.basicConfig(level=logging.DEBUG)  # See all incoming messages

    # Call seed if in start.py
    from handlers.startup import seed_batches
    await seed_batches()

    print("Bot starting with admin handlers registered...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())