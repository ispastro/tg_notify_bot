import asyncio
import logging
import sys

# Configure logging as early as possible so handler logs are visible
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(name)s:%(message)s")

from loader import bot, dp

# Import handlers after logging is configured so their logging appears
# Import admin first so its debug/general handlers register early and can observe commands
import handlers.admin  # registers admin handlers
import handlers.users  # registers /start and message handlers
from handlers.startup import seed_batches


async def main():
    logging.getLogger(__name__).info("Starting bot main()")

    # Confirm bot identity and that handler modules are loaded
    me = await bot.get_me()
    logging.getLogger(__name__).info(f"Bot running as: {me.username} (id={me.id})")
    # Log configured SUPER_ADMIN_ID for cross-check
    try:
        from config import SUPER_ADMIN_ID
        logging.getLogger(__name__).info(f"SUPER_ADMIN_ID (env) = {SUPER_ADMIN_ID}")
    except Exception:
        logging.getLogger(__name__).warning("SUPER_ADMIN_ID not set or invalid in env")
    # Check if a webhook is set (if webhook is set, long-polling won't receive updates)
    try:
        webhook_info = await bot.get_webhook_info()
        url = getattr(webhook_info, 'url', None)
        logging.getLogger(__name__).info(f"Webhook URL configured: {url}")
    except Exception as e:
        logging.getLogger(__name__).warning(f"Could not get webhook info: {e}")
    logging.getLogger(__name__).info("handlers.users imported: %s", 'handlers.users' in sys.modules)
    logging.getLogger(__name__).info("handlers.admin imported: %s", 'handlers.admin' in sys.modules)

    await seed_batches()

    # Start polling (this will block)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
