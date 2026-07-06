from __future__ import annotations

from fastapi import Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.db import SessionLocal
from bot.database.crud import get_or_create_user, reset_daily_quota_if_needed
from bot.database.models import User
from bot.utils.telegram_auth import verify_session_token, InvalidInitData


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


async def get_current_user(
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        user_id = verify_session_token(token)
    except InvalidInitData as e:
        raise HTTPException(401, f"Invalid session: {e}")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(401, "User not found — re-open the mini app")

    await reset_daily_quota_if_needed(db, user)
    return user
