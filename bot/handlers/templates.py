"""
/templates command: lists saved templates and offers a quick "From file" flow
that lets a user create a photo-watermark template by simply sending a PNG,
without opening the Mini App — mirrors the reference bot's fastest path.

The full-featured template editor (sliders, live preview, text templates) is
the Mini App; this module intentionally stays minimal.
"""
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, CallbackQuery
)

from bot.config import WEBAPP_URL, WATERMARKS_DIR
from bot.database.db import SessionLocal
from bot.database import crud

# In-memory per-user flag: are we waiting for a PNG to create a template?
_awaiting_upload: set[int] = set()


def _templates_keyboard(templates, default_id):
    rows = []
    for t in templates:
        mark = "✅ " if t.id == default_id else ""
        rows.append([InlineKeyboardButton(f"{mark}{t.name}", callback_data=f"tpl:show:{t.id}")])
    rows.append([InlineKeyboardButton("📤 From file (send PNG)", callback_data="tpl:fromfile")])
    rows.append([InlineKeyboardButton("🎨 Open editor", web_app=WebAppInfo(url=WEBAPP_URL))])
    return InlineKeyboardMarkup(rows)


@Client.on_message(filters.command("templates") & filters.private)
async def templates_cmd(client: Client, message: Message):
    async with SessionLocal() as session:
        user = await crud.get_or_create_user(session, message.from_user.id, message.from_user.username,
                                              message.from_user.first_name)
        templates = await crud.list_templates(session, user.id)

    if not templates:
        await message.reply(
            "🖼️ **Watermark templates**\n\nYou don't have any yet. Send me a PNG (as a document, "
            "no compression) to create a photo-watermark template instantly, or open the full editor.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 From file (send PNG)", callback_data="tpl:fromfile")],
                [InlineKeyboardButton("🎨 Open editor", web_app=WebAppInfo(url=WEBAPP_URL))],
            ]),
        )
        return

    await message.reply(
        f"🖼️ **Watermark templates** ({len(templates)})\nTap one to view, or add a new one.",
        reply_markup=_templates_keyboard(templates, user.default_template_id),
    )


@Client.on_callback_query(filters.regex(r"^tpl:fromfile$"))
async def tpl_fromfile(client: Client, cb: CallbackQuery):
    _awaiting_upload.add(cb.from_user.id)
    await cb.answer()
    await cb.message.reply(
        "📎 Send the watermark PNG as a **document** (no compression), or /cancel to abort."
    )


@Client.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client: Client, message: Message):
    _awaiting_upload.discard(message.from_user.id)
    await message.reply("Cancelled.")


@Client.on_message(filters.document & filters.private)
async def receive_template_png(client: Client, message: Message):
    if message.from_user.id not in _awaiting_upload:
        return  # not in the upload flow; ignore (media.py handles generic documents if needed)
    if not (message.document.mime_type or "").startswith("image/"):
        await message.reply("That doesn't look like an image. Please send a PNG document, or /cancel.")
        return

    _awaiting_upload.discard(message.from_user.id)
    dest = WATERMARKS_DIR / f"{message.from_user.id}_{message.document.file_unique_id}.png"
    await message.download(file_name=str(dest))

    async with SessionLocal() as session:
        user = await crud.get_or_create_user(session, message.from_user.id, message.from_user.username,
                                              message.from_user.first_name)
        limit = crud.plan_template_limit(user.plan)
        existing = await crud.list_templates(session, user.id)
        if len(existing) >= limit:
            await message.reply(f"⚠️ Template limit reached for your plan ({limit}). Upgrade with /profile.")
            return

        name = f"Template {len(existing) + 1}"
        tmpl = await crud.create_template(
            session, owner_id=user.id, name=name, kind="photo", image_path=str(dest),
            position="bottom-right", offset_x_pct=5, offset_y_pct=5, width_pct=25,
            opacity_pct=100, rotation_deg=0,
        )
        if not user.default_template_id:
            await crud.set_default_template(session, user, tmpl.id)

    await message.reply(
        f"✅ **{name}** created from your image, placed bottom-right at 25% width.\n\n"
        "Open the Studio app to fine-tune position, size, opacity, or rotation with live preview.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎨 Fine-tune in editor", web_app=WebAppInfo(url=WEBAPP_URL))],
        ]),
    )


@Client.on_callback_query(filters.regex(r"^tpl:show:(\d+)$"))
async def tpl_show(client: Client, cb: CallbackQuery):
    template_id = int(cb.data.split(":")[-1])
    async with SessionLocal() as session:
        tmpl = await crud.get_template(session, template_id, cb.from_user.id)
    if not tmpl:
        await cb.answer("Not found", show_alert=True)
        return
    await cb.answer()
    details = (
        f"**{tmpl.name}**\n"
        f"Type: {tmpl.kind}\n"
        f"Position: {tmpl.position}\n"
        f"Width: {tmpl.width_pct}%  ·  Opacity: {tmpl.opacity_pct}%  ·  Rotation: {tmpl.rotation_deg}°\n"
        f"Screen movement: {'on' if tmpl.screen_movement else 'off'}"
    )
    await cb.message.reply(
        details,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎨 Edit in Studio", web_app=WebAppInfo(url=WEBAPP_URL))],
        ]),
    )
