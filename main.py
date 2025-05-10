import os
import logging
import asyncio
from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)
from aiohttp import web

from handlers import (
    start, status, help_command, id_command,
    message_handler, reload_config,
    weekly_summary, clear_homework_log,
    list_senders, clear_senders
)

# Load environment variables from .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_IDS = set(map(int, os.getenv("ADMIN_CHAT_IDS", "").split(",")))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8443"))
WEBHOOK_PATH = f"/{BOT_TOKEN}"
ROUTES_MAP = os.getenv("ROUTES_MAP")

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Start-up notification
async def notify_admins_on_startup(app: web.Application):
    for admin_id in ADMIN_CHAT_IDS:
        try:
            await app.bot.send_message(admin_id, "✅ Bot has started and webhook is live!")
        except Exception as e:
            logging.warning(f"Failed to notify admin {admin_id}: {e}")

# Webhook setup
async def webhook_handler(request):
    data = await request.json()
    await request.app["bot"].process_update(data)
    return web.Response(text="OK")

async def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Inject bot_data values
    application.bot_data["ROUTES"] = ROUTES_MAP
    application.bot_data["ADMIN_CHAT_IDS"] = ADMIN_CHAT_IDS

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("reload_config", reload_config))
    application.add_handler(CommandHandler("weekly_summary", weekly_summary))
    application.add_handler(CommandHandler("clear_homework_log", clear_homework_log))
    application.add_handler(CommandHandler("list_senders", list_senders))
    application.add_handler(CommandHandler("clear_senders", clear_senders))

    # Message handler (text, audio, voice, photo)
    application.add_handler(MessageHandler(
        filters.TEXT | filters.VOICE | filters.AUDIO | filters.PHOTO, message_handler
    ))

    # Webhook app
    app = web.Application()
    app["bot"] = application
    app.router.add_post(WEBHOOK_PATH, webhook_handler)

    # Set webhook
    await application.bot.set_webhook(url=WEBHOOK_URL + WEBHOOK_PATH)
    await notify_admins_on_startup(application)

    # Start aiohttp server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBHOOK_PORT)
    await site.start()

    print(f"Bot running via webhook at {WEBHOOK_URL}{WEBHOOK_PATH}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())