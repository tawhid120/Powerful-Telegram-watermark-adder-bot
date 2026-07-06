from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import (
    get_or_create_user, plan_template_limit, plan_channel_limit
)
from bot.utils.telegram_auth import validate_init_data, issue_session_token, InvalidInitData
from webapp_server.deps import get_db
from webapp_server.schemas import AuthRequest, AuthResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("", response_model=AuthResponse)
async def authenticate(payload: AuthRequest, db: AsyncSession = Depends(get_db)):
    try:
        tg_user = validate_init_data(payload.init_data)
    except InvalidInitData as e:
        raise HTTPException(401, f"Telegram auth failed: {e}")

    user = await get_or_create_user(
        db,
        tg_id=tg_user["id"],
        username=tg_user.get("username"),
        first_name=tg_user.get("first_name"),
    )
    token = issue_session_token(user.id)
    return AuthResponse(
        token=token,
        user_id=user.id,
        plan=user.plan,
        template_limit=plan_template_limit(user.plan),
        channel_limit=plan_channel_limit(user.plan),
    )
