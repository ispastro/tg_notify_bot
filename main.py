import asyncio
import logging
from loader import bot, dp
import handlers.users  # register handlers here

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
