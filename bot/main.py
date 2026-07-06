"""
WMark Bot — main entrypoint.
Run with:  python -m bot.main
"""
import asyncio
import logging

from pyrogram import Client
from pyrogram.types import BotCommand

from bot.config import API_ID, API_HASH, BOT_TOKEN
from bot.database.db import init_db
from bot.handlers import start, templates, channels_admin, media, tails, profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("wmarkbot")

app = Client(
    "wmarkbot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=dict(root="bot/handlers"),
)


async def set_bot_commands():
    await app.set_bot_commands([
        BotCommand("start", "Open the watermark studio"),
        BotCommand("templates", "Manage watermark templates"),
        BotCommand("tails", "Manage video tails"),
        BotCommand("channels", "Connect a channel for auto-watermarking"),
        BotCommand("profile", "View plan and usage"),
        BotCommand("cancel", "Cancel the current action"),
    ])


async def main():
    await init_db()
    await app.start()
    await set_bot_commands()
    me = await app.get_me()
    logger.info(f"WMark Bot started as @{me.username}")
    await asyncio.Event().wait()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
