"""
/start command — greets the user and offers the Mini App button, mirroring
the reference bot's welcome flow but branded as WMark Studio.
"""
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from bot.config import WEBAPP_URL
from bot.database.db import SessionLocal
from bot.database import crud


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎨 Open Watermark Studio", web_app=WebAppInfo(url=WEBAPP_URL))],
        [
            InlineKeyboardButton("🖼️ Templates", callback_data="menu:templates"),
            InlineKeyboardButton("🎬 Tails", callback_data="menu:tails"),
        ],
        [
            InlineKeyboardButton("📺 Channels", callback_data="menu:channels"),
            InlineKeyboardButton("👤 Profile", callback_data="menu:profile"),
        ],
    ])


@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    async with SessionLocal() as session:
        await crud.get_or_create_user(
            session, tg_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )

    await message.reply(
        "👋 **Welcome to WMark Studio!**\n\n"
        "I add watermarks — text or logo — to your photos and videos, "
        "right from a fast in-app editor. I can also auto-watermark every "
        "post in a channel where you add me as admin.\n\n"
        "Tap **Open Watermark Studio** below to get started, or just send me "
        "a photo/video directly and I'll ask which template to use.",
        reply_markup=main_menu_keyboard(),
    )


@Client.on_callback_query(filters.regex(r"^menu:"))
async def menu_router(client: Client, callback_query):
    dest = callback_query.data.split(":", 1)[1]
    labels = {
        "templates": "Use /templates to manage your watermark templates, or open the Studio app.",
        "tails": "Use /tails to manage video tails, or open the Studio app.",
        "channels": "Use /channels to connect a channel, or open the Studio app.",
        "profile": "Use /profile to see your plan and usage.",
    }
    await callback_query.answer()
    await callback_query.message.reply(labels.get(dest, "Open the Studio app for the full experience."))
