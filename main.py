import asyncio
import logging
from loader import bot, dp
import handlers.users  # register handlers here
from handlers.startup import seed_batches

async def main():
    logging.basicConfig(level=logging.INFO)

    await seed_batches()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
