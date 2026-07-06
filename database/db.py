"""
Async database engine + session factory, shared by both the bot process
and the FastAPI webapp process.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from bot.config import DATABASE_URL
from bot.database.models import Base

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db():
    """Create all tables if they don't exist. Call once at startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session():
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
