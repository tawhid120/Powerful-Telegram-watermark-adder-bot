"""
/profile command: shows plan, usage, and lets the user request a plan upgrade
(actual payment integration is a stub — wire up Telegram Payments or Stars here).
"""
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from bot.database.db import SessionLocal
from bot.database import crud
from bot.config import ADMIN_IDS, PLAN_LIMITS


def _plan_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Lite (free)", callback_data="plan:free"),
            InlineKeyboardButton("Normal", callback_data="plan:normal"),
        ],
        [InlineKeyboardButton("Pro", callback_data="plan:pro")],
    ])


@Client.on_message(filters.command("profile") & filters.private)
async def profile_cmd(client: Client, message: Message):
    async with SessionLocal() as session:
        user = await crud.get_or_create_user(session, message.from_user.id, message.from_user.username,
                                              message.from_user.first_name)
        await crud.reset_daily_quota_if_needed(session, user)
        templates = await crud.list_templates(session, user.id)
        channels = await crud.list_channels(session, user.id)

    used_mb = user.daily_bytes_used / (1024 * 1024)
    limit_mb = PLAN_LIMITS[user.plan]["daily_mb"]

    text = (
        f"👤 **Profile**\n\n"
        f"Plan: **{user.plan.capitalize()}**\n"
        f"Today's traffic: {used_mb:.1f} MB / {limit_mb} MB\n"
        f"Templates: {len(templates)} / {crud.plan_template_limit(user.plan)}\n"
        f"Channels: {len(channels)} / {crud.plan_channel_limit(user.plan)}\n\n"
        f"Pick a plan to see purchase options:"
    )
    await message.reply(text, reply_markup=_plan_keyboard())


@Client.on_callback_query(filters.regex(r"^plan:(free|normal|pro)$"))
async def plan_select(client: Client, cb: CallbackQuery):
    plan = cb.data.split(":")[1]
    await cb.answer()
    if plan == "free":
        await cb.message.reply("Lite is the free plan — you're already eligible, no action needed.")
        return
    # Stub: replace with real Telegram Stars / payment provider integration.
    await cb.message.reply(
        f"To upgrade to **{plan.capitalize()}**, payment isn't wired up yet in this template project. "
        f"Hook up Telegram Payments or Telegram Stars in `bot/handlers/profile.py` "
        f"(`plan_select`) to process this upgrade and call a `set_plan` CRUD helper."
    )
