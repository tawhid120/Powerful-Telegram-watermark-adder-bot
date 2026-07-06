"""
Channel integration:
  1. Detects when the bot is promoted to admin in a channel and registers it
     to whichever user added it (best-effort: the user who sent /start most
     recently in that channel's linked chat, or via explicit /connect).
  2. Listens for new channel posts (photo/video) and auto-applies that
     channel's configured template, replacing the original post with the
     watermarked version (edit-in-place isn't possible for media, so we
     delete + repost).
"""
from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from bot.config import WEBAPP_URL, UPLOADS_DIR
from bot.database.db import SessionLocal
from bot.database import crud
from bot.utils.processor import process_file


@Client.on_chat_member_updated()
async def on_bot_promoted(client: Client, event: ChatMemberUpdated):
    """When the bot is added as admin to a channel, register it under the user who promoted it."""
    me = await client.get_me()
    if event.new_chat_member and event.new_chat_member.user.id == me.id:
        if event.new_chat_member.status in ("administrator",):
            promoter_id = event.from_user.id if event.from_user else None
            if not promoter_id:
                return
            async with SessionLocal() as session:
                user = await crud.get_or_create_user(session, promoter_id)
                channels = await crud.list_channels(session, user.id)
                limit = crud.plan_channel_limit(user.plan)
                if len(channels) >= limit:
                    try:
                        await client.send_message(
                            promoter_id,
                            f"⚠️ I was added to **{event.chat.title}** but your plan's channel limit "
                            f"({limit}) is reached. Upgrade with /profile to activate auto-watermarking here."
                        )
                    except Exception:
                        pass
                    return
                await crud.create_channel(session, user.id, event.chat.id, event.chat.title or "Channel")
            try:
                await client.send_message(
                    promoter_id,
                    f"✅ Connected **{event.chat.title}**. Open the Studio app to assign a watermark template to it.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎨 Set up channel", web_app=WebAppInfo(url=WEBAPP_URL))]]),
                )
            except Exception:
                pass  # user may have blocked the bot in DM


@Client.on_message((filters.photo | filters.video) & filters.channel)
async def auto_watermark_channel_post(client: Client, message: Message):
    async with SessionLocal() as session:
        channel = await crud.get_channel_by_chat_id(session, message.chat.id)
        if not channel or not channel.template_id:
            return
        template = await crud.get_template(session, channel.template_id, channel.owner_id)
        tail = None
        if channel.tail_id:
            tails = await crud.list_tails(session, channel.owner_id)
            tail = next((t for t in tails if t.id == channel.tail_id), None)
        if not template:
            return

    local_path = UPLOADS_DIR / f"chan_{message.chat.id}_{message.id}"
    try:
        downloaded = await message.download(file_name=str(local_path))
        output_path = process_file(downloaded, template, tail)

        caption = message.caption or ""
        if str(output_path).lower().endswith((".mp4", ".mov", ".mkv", ".webm")):
            await client.send_video(message.chat.id, str(output_path), caption=caption)
        else:
            await client.send_photo(message.chat.id, str(output_path), caption=caption)
        await message.delete()
    except Exception:
        # Fail safe: never delete the original if watermarking failed.
        pass
    finally:
        try:
            local_path.unlink(missing_ok=True)
        except Exception:
            pass


@Client.on_message(filters.command("channels") & filters.private)
async def channels_cmd(client: Client, message: Message):
    async with SessionLocal() as session:
        user = await crud.get_or_create_user(session, message.from_user.id, message.from_user.username,
                                              message.from_user.first_name)
        channels = await crud.list_channels(session, user.id)

    limit = crud.plan_channel_limit(user.plan)
    if not channels:
        await message.reply(
            f"📺 **Channels** (0/{limit})\n\nAdd me as **admin** to a channel and I'll register it here "
            "automatically. Then open the Studio app to assign a watermark template to it.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎨 Open Studio", web_app=WebAppInfo(url=WEBAPP_URL))]]),
        )
        return

    lines = [f"• {c.title} — {'✅ active' if c.is_active else '⏸ paused'}" for c in channels]
    await message.reply(
        f"📺 **Channels** ({len(channels)}/{limit})\n\n" + "\n".join(lines) +
        "\n\nOpen the Studio app to change templates or pause a channel.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎨 Open Studio", web_app=WebAppInfo(url=WEBAPP_URL))]]),
    )
