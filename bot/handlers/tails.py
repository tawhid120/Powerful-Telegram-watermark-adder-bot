"""
/tails command: manage "video tails" — short clips/images appended to the
end of watermarked videos. Quick list + delete via bot; full upload flow
lives in the Mini App (multipart upload is much easier there than in chat).
"""
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, CallbackQuery

from bot.config import WEBAPP_URL
from bot.database.db import SessionLocal
from bot.database import crud


@Client.on_message(filters.command("tails") & filters.private)
async def tails_cmd(client: Client, message: Message):
    async with SessionLocal() as session:
        user = await crud.get_or_create_user(session, message.from_user.id, message.from_user.username,
                                              message.from_user.first_name)
        tails = await crud.list_tails(session, user.id)

    if not tails:
        await message.reply(
            "🎬 **Video tails**\n\nNo tails yet. Open the Studio app to upload a short clip or image "
            "that gets appended to the end of your watermarked videos.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎨 Open Studio", web_app=WebAppInfo(url=WEBAPP_URL))]]),
        )
        return

    rows = [[InlineKeyboardButton(f"🗑️ {t.name}", callback_data=f"tail:del:{t.id}")] for t in tails]
    rows.append([InlineKeyboardButton("🎨 Open Studio to add more", web_app=WebAppInfo(url=WEBAPP_URL))])
    await message.reply(f"🎬 **Video tails** ({len(tails)})\nTap to delete.", reply_markup=InlineKeyboardMarkup(rows))


@Client.on_callback_query(filters.regex(r"^tail:del:(\d+)$"))
async def tail_delete(client: Client, cb: CallbackQuery):
    tail_id = int(cb.data.split(":")[-1])
    async with SessionLocal() as session:
        ok = await crud.delete_tail(session, tail_id, cb.from_user.id)
    await cb.answer("Deleted" if ok else "Not found", show_alert=not ok)
    if ok:
        await cb.message.delete()
