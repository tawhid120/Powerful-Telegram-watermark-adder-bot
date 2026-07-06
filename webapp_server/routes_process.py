from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import UPLOADS_DIR, MAX_UPLOAD_MB
from bot.database import crud
from bot.database.models import User
from bot.utils.processor import process_file, detect_media_type
from webapp_server.deps import get_db, get_current_user

router = APIRouter(prefix="/api/process", tags=["process"])

MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


@router.post("")
async def process_media(
    template_id: int = Form(...),
    tail_id: int | None = Form(None),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    template = await crud.get_template(db, template_id, user.id)
    if not template:
        raise HTTPException(404, "Template not found")

    tail = None
    if tail_id:
        tails = await crud.list_tails(db, user.id)
        tail = next((t for t in tails if t.id == tail_id), None)
        if not tail:
            raise HTTPException(404, "Tail not found")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large. Max {MAX_UPLOAD_MB}MB per upload.")

    daily_limit = crud.plan_limit_bytes(user.plan)
    if user.daily_bytes_used + len(content) > daily_limit:
        remaining_mb = max(0, (daily_limit - user.daily_bytes_used) // (1024 * 1024))
        raise HTTPException(429, f"Daily quota exceeded. {remaining_mb}MB remaining today. Upgrade for more.")

    ext = Path(file.filename or "").suffix.lower() or ".bin"
    input_path = UPLOADS_DIR / f"{user.id}_{uuid.uuid4().hex}{ext}"
    input_path.write_bytes(content)

    try:
        media_type = detect_media_type(input_path)
    except ValueError as e:
        input_path.unlink(missing_ok=True)
        raise HTTPException(400, str(e))

    job = await crud.create_job(db, owner_id=user.id, media_type=media_type, source="webapp",
                                 template_id=template.id, input_bytes=len(content))

    try:
        output_path = process_file(input_path, template, tail)
        await crud.finish_job(db, job, output_path=str(output_path))
        await crud.add_usage(db, user, len(content))
    except Exception as e:
        await crud.finish_job(db, job, output_path=None, error=str(e))
        raise HTTPException(500, f"Processing failed: {e}")
    finally:
        input_path.unlink(missing_ok=True)

    media_type_for_ext = "video/mp4" if media_type == "video" else "image/png"
    return FileResponse(output_path, media_type=media_type_for_ext, filename=output_path.name)
