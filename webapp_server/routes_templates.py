from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import WATERMARKS_DIR, POSITIONS
from bot.database import crud
from bot.database.models import User
from webapp_server.deps import get_db, get_current_user
from webapp_server.schemas import TemplateOut, TemplateIn

router = APIRouter(prefix="/api/templates", tags=["templates"])

ALLOWED_IMAGE_TYPES = {"image/png", "image/webp", "image/jpeg"}


@router.get("", response_model=list[TemplateOut])
async def list_templates(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await crud.list_templates(db, user.id)


@router.post("", response_model=TemplateOut)
async def create_template(
    name: str = Form(...),
    kind: str = Form(...),
    text_content: str | None = Form(None),
    font_family: str = Form("default"),
    font_size: int = Form(32),
    font_color: str = Form("#FFFFFF"),
    position: str = Form("bottom-right"),
    offset_x_pct: float = Form(5.0),
    offset_y_pct: float = Form(5.0),
    width_pct: float = Form(25.0),
    opacity_pct: float = Form(100.0),
    rotation_deg: float = Form(0.0),
    screen_movement: bool = Form(False),
    image: UploadFile | None = File(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if position not in POSITIONS:
        raise HTTPException(400, f"invalid position, must be one of {POSITIONS}")

    existing = await crud.list_templates(db, user.id)
    limit = crud.plan_template_limit(user.plan)
    if len(existing) >= limit:
        raise HTTPException(403, f"Template limit reached for your plan ({limit}). Upgrade to add more.")

    image_path = None
    if kind == "photo":
        if not image:
            raise HTTPException(400, "image file required for kind='photo'")
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(400, "Only PNG/WEBP/JPEG accepted — use PNG with transparency for best results")
        ext = ".png" if image.content_type == "image/png" else Path(image.filename or "").suffix or ".png"
        dest = WATERMARKS_DIR / f"{user.id}_{uuid.uuid4().hex}{ext}"
        content = await image.read()
        dest.write_bytes(content)
        image_path = str(dest)
    elif kind == "text" and not text_content:
        raise HTTPException(400, "text_content required for kind='text'")

    tmpl = await crud.create_template(
        db, owner_id=user.id, name=name, kind=kind, image_path=image_path,
        text_content=text_content, font_family=font_family, font_size=font_size,
        font_color=font_color, position=position, offset_x_pct=offset_x_pct,
        offset_y_pct=offset_y_pct, width_pct=width_pct, opacity_pct=opacity_pct,
        rotation_deg=rotation_deg, screen_movement=screen_movement,
    )
    return tmpl


@router.put("/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: int,
    body: TemplateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tmpl = await crud.get_template(db, template_id, user.id)
    if not tmpl:
        raise HTTPException(404, "Template not found")
    if body.position not in POSITIONS:
        raise HTTPException(400, f"invalid position, must be one of {POSITIONS}")
    updated = await crud.update_template(db, tmpl, **body.model_dump(exclude={"kind"}))
    return updated


@router.delete("/{template_id}")
async def delete_template(template_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ok = await crud.delete_template(db, template_id, user.id)
    if not ok:
        raise HTTPException(404, "Template not found")
    return {"deleted": True}


@router.get("/{template_id}/thumb")
async def template_thumb(template_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tmpl = await crud.get_template(db, template_id, user.id)
    if not tmpl or not tmpl.image_path:
        raise HTTPException(404, "No image for this template")
    return FileResponse(tmpl.image_path)


@router.post("/{template_id}/set-default")
async def set_default(template_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tmpl = await crud.get_template(db, template_id, user.id)
    if not tmpl:
        raise HTTPException(404, "Template not found")
    await crud.set_default_template(db, user, template_id)
    return {"default_template_id": template_id}
