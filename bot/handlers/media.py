"""
Handles photos/videos sent directly to the bot in a private chat: applies
the user's default template (or lets them pick one) and sends back the
watermarked result. This is the fastest path for repeat use, complementing
the Mini App's richer editor.
"""
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from bot.config import UPLOADS_DIR
from bot.database.db import SessionLocal
from bot.database import crud
from bot.utils.processor import process_file

# Temporarily remembers which file a user is choosing a template for.
_pending_files: dict[int, str] = {}


@Client.on_message((filters.photo | filters.video) & filters.private)
async def handle_media(client: Client, message: Message):
    async with SessionLocal() as session:
        user = await crud.get_or_create_user(session, message.from_user.id, message.from_user.username,
                                              message.from_user.first_name)
        await crud.reset_daily_quota_if_needed(session, user)
        templates = await crud.list_templates(session, user.id)

    if not templates:
        await message.reply(
            "You don't have a watermark template yet. Use /templates to create one first "
            "(send a PNG, or open the Studio editor)."
        )
        return

    status = await message.reply("⬇️ Downloading…")
    local_path = UPLOADS_DIR / f"{message.from_user.id}_{message.id}"
    downloaded = await message.download(file_name=str(local_path))
    _pending_files[message.from_user.id] = downloaded

    if user.default_template_id:
        await status.edit("🎨 Applying your default watermark…")
        await _apply_and_send(client, message.chat.id, message.from_user.id, user.default_template_id, status)
        return

    buttons = [[InlineKeyboardButton(t.name, callback_data=f"apply:{t.id}")] for t in templates]
    await status.edit("Pick a template to apply:", reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^apply:(\d+)$"))
async def apply_template_cb(client: Client, cb: CallbackQuery):
    template_id = int(cb.data.split(":")[1])
    await cb.answer()
    await cb.message.edit("🎨 Applying watermark…")
    await _apply_and_send(client, cb.message.chat.id, cb.from_user.id, template_id, cb.message)


async def _apply_and_send(client: Client, chat_id: int, user_id: int, template_id: int, status_message):
    local_path = _pending_files.get(user_id)
    if not local_path:
        await status_message.edit("⚠️ That file expired, please resend it.")
        return

    async with SessionLocal() as session:
        from bot.database.models import User
        user = await session.get(User, user_id)
        template = await crud.get_template(session, template_id, user_id)
        if not template:
            await status_message.edit("⚠️ Template not found.")
            return

        import os
        file_size = os.path.getsize(local_path)
        daily_limit = crud.plan_limit_bytes(user.plan)
        if user.daily_bytes_used + file_size > daily_limit:
            remaining = max(0, (daily_limit - user.daily_bytes_used) // (1024 * 1024))
            await status_message.edit(f"⚠️ Daily quota exceeded. {remaining}MB remaining today. Upgrade with /profile.")
            return

        from bot.utils.processor import detect_media_type
        media_type = detect_media_type(local_path)
        job = await crud.create_job(session, user_id, media_type=media_type,
                                     source="bot", template_id=template.id, input_bytes=file_size)
        try:
            output_path = process_file(local_path, template)
            await crud.finish_job(session, job, output_path=str(output_path))
            await crud.add_usage(session, user, file_size)
        except Exception as e:
            await crud.finish_job(session, job, output_path=None, error=str(e))
            await status_message.edit(f"❌ Processing failed: {e}")
            return

    try:
        if str(output_path).lower().endswith((".mp4", ".mov", ".mkv", ".webm")):
            await client.send_video(chat_id, str(output_path), caption="✅ Watermarked")
        else:
            await client.send_document(chat_id, str(output_path), caption="✅ Watermarked (sent as file to preserve quality)")
        await status_message.delete()
    except Exception as e:
        await status_message.edit(f"❌ Failed to send result: {e}")
    finally:
        _pending_files.pop(user_id, None)
