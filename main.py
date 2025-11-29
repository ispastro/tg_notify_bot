# main.py
import asyncio
import os
from aiohttp import web
from loader import bot, dp
import handlers.users
import handlers.admin
import handlers.schedule
from handlers.startup import seed_batches

async def health_check(request):
    return web.Response(text="Bot is alive!", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server started on port {port}")

async def main():
    from services.scheduler import scheduler_loop
    from utils.set_bot_commands import set_default_commands, set_admin_commands
    
    # 1. Start Web Server (for Render/UptimeRobot)
    await start_web_server()
    
    # 2. Seed Data
    await seed_batches()
    
    # 3. Set Commands
    await set_default_commands(bot)
    await set_admin_commands(bot)
    
    # 4. Start Scheduler
    asyncio.create_task(scheduler_loop(bot))
    
    print("Bot starting...")
    
    # 5. Start Polling
    # Drop pending updates to prevent conflict on restart
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())