from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import STORAGE_DIR
from bot.database import crud
from bot.database.models import User
from webapp_server.deps import get_db, get_current_user
from webapp_server.schemas import ProfileOut, ChannelOut, ChannelIn

router = APIRouter(prefix="/api", tags=["misc"])

TAILS_DIR = STORAGE_DIR / "tails"
TAILS_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/profile", response_model=ProfileOut)
async def profile(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    templates = await crud.list_templates(db, user.id)
    channels = await crud.list_channels(db, user.id)
    return ProfileOut(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        plan=user.plan,
        daily_bytes_used=user.daily_bytes_used,
        daily_limit_bytes=crud.plan_limit_bytes(user.plan),
        template_count=len(templates),
        template_limit=crud.plan_template_limit(user.plan),
        channel_count=len(channels),
        channel_limit=crud.plan_channel_limit(user.plan),
    )


@router.get("/tails")
async def list_tails(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tails = await crud.list_tails(db, user.id)
    return [{"id": t.id, "name": t.name, "is_default": t.is_default} for t in tails]


@router.post("/tails")
async def create_tail(
    name: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ext = Path(file.filename or "").suffix.lower() or ".mp4"
    dest = TAILS_DIR / f"{user.id}_{uuid.uuid4().hex}{ext}"
    dest.write_bytes(await file.read())
    tail = await crud.create_tail(db, user.id, name, str(dest))
    return {"id": tail.id, "name": tail.name}


@router.delete("/tails/{tail_id}")
async def delete_tail(tail_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ok = await crud.delete_tail(db, tail_id, user.id)
    if not ok:
        raise HTTPException(404, "Tail not found")
    return {"deleted": True}


@router.get("/channels", response_model=list[ChannelOut])
async def list_channels(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await crud.list_channels(db, user.id)


@router.put("/channels/{channel_id}", response_model=ChannelOut)
async def update_channel(
    channel_id: int, body: ChannelIn,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    channels = await crud.list_channels(db, user.id)
    channel = next((c for c in channels if c.id == channel_id), None)
    if not channel:
        raise HTTPException(404, "Channel not found")
    channel.template_id = body.template_id
    channel.tail_id = body.tail_id
    channel.is_active = body.is_active
    await db.commit()
    return channel


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ok = await crud.delete_channel(db, channel_id, user.id)
    if not ok:
        raise HTTPException(404, "Channel not found")
    return {"deleted": True}
