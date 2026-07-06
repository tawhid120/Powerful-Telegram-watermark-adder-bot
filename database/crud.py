"""
CRUD helper functions shared by the bot and the webapp API.
Keeping all queries here avoids duplicating logic across the two entry points.
"""
from __future__ import annotations

import datetime as dt
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import PLAN_LIMITS
from bot.database.models import User, Template, Tail, Channel, Job


# ---------- Users ----------

async def get_or_create_user(session: AsyncSession, tg_id: int, username: str | None = None,
                              first_name: str | None = None, referred_by: int | None = None) -> User:
    user = await session.get(User, tg_id)
    if user is None:
        user = User(id=tg_id, username=username, first_name=first_name, referred_by=referred_by)
        session.add(user)
        await session.commit()
    else:
        changed = False
        if username and user.username != username:
            user.username = username
            changed = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if changed:
            await session.commit()
    return user


async def reset_daily_quota_if_needed(session: AsyncSession, user: User) -> None:
    now = dt.datetime.utcnow()
    if (now - user.daily_reset_at) > dt.timedelta(hours=24):
        user.daily_bytes_used = 0
        user.daily_reset_at = now
        await session.commit()


async def add_usage(session: AsyncSession, user: User, num_bytes: int) -> None:
    user.daily_bytes_used += num_bytes
    await session.commit()


def plan_limit_bytes(plan: str) -> int:
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])["daily_mb"] * 1024 * 1024


def plan_template_limit(plan: str) -> int:
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])["templates"]


def plan_channel_limit(plan: str) -> int:
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])["channels"]


# ---------- Templates ----------

async def list_templates(session: AsyncSession, owner_id: int) -> list[Template]:
    res = await session.execute(
        select(Template).where(Template.owner_id == owner_id).order_by(Template.id)
    )
    return list(res.scalars().all())


async def get_template(session: AsyncSession, template_id: int, owner_id: int) -> Template | None:
    res = await session.execute(
        select(Template).where(Template.id == template_id, Template.owner_id == owner_id)
    )
    return res.scalar_one_or_none()


async def create_template(session: AsyncSession, owner_id: int, **kwargs) -> Template:
    tmpl = Template(owner_id=owner_id, **kwargs)
    session.add(tmpl)
    await session.commit()
    await session.refresh(tmpl)
    return tmpl


async def update_template(session: AsyncSession, template: Template, **kwargs) -> Template:
    for k, v in kwargs.items():
        setattr(template, k, v)
    await session.commit()
    return template


async def delete_template(session: AsyncSession, template_id: int, owner_id: int) -> bool:
    tmpl = await get_template(session, template_id, owner_id)
    if not tmpl:
        return False
    await session.delete(tmpl)
    await session.commit()
    return True


async def set_default_template(session: AsyncSession, user: User, template_id: int | None) -> None:
    user.default_template_id = template_id
    await session.commit()


# ---------- Tails ----------

async def list_tails(session: AsyncSession, owner_id: int) -> list[Tail]:
    res = await session.execute(select(Tail).where(Tail.owner_id == owner_id).order_by(Tail.id))
    return list(res.scalars().all())


async def create_tail(session: AsyncSession, owner_id: int, name: str, file_path: str) -> Tail:
    tail = Tail(owner_id=owner_id, name=name, file_path=file_path)
    session.add(tail)
    await session.commit()
    await session.refresh(tail)
    return tail


async def delete_tail(session: AsyncSession, tail_id: int, owner_id: int) -> bool:
    res = await session.execute(select(Tail).where(Tail.id == tail_id, Tail.owner_id == owner_id))
    tail = res.scalar_one_or_none()
    if not tail:
        return False
    await session.delete(tail)
    await session.commit()
    return True


# ---------- Channels ----------

async def list_channels(session: AsyncSession, owner_id: int) -> list[Channel]:
    res = await session.execute(select(Channel).where(Channel.owner_id == owner_id).order_by(Channel.id))
    return list(res.scalars().all())


async def get_channel_by_chat_id(session: AsyncSession, chat_id: int) -> Channel | None:
    res = await session.execute(select(Channel).where(Channel.chat_id == chat_id, Channel.is_active == True))  # noqa: E712
    return res.scalar_one_or_none()


async def create_channel(session: AsyncSession, owner_id: int, chat_id: int, title: str,
                          template_id: int | None = None) -> Channel:
    ch = Channel(owner_id=owner_id, chat_id=chat_id, title=title, template_id=template_id)
    session.add(ch)
    await session.commit()
    await session.refresh(ch)
    return ch


async def delete_channel(session: AsyncSession, channel_id: int, owner_id: int) -> bool:
    res = await session.execute(select(Channel).where(Channel.id == channel_id, Channel.owner_id == owner_id))
    ch = res.scalar_one_or_none()
    if not ch:
        return False
    await session.delete(ch)
    await session.commit()
    return True


# ---------- Jobs ----------

async def create_job(session: AsyncSession, owner_id: int, media_type: str, source: str,
                      template_id: int | None, input_bytes: int) -> Job:
    job = Job(owner_id=owner_id, media_type=media_type, source=source,
              template_id=template_id, input_bytes=input_bytes, status="processing")
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def finish_job(session: AsyncSession, job: Job, output_path: str | None, error: str | None = None) -> None:
    job.status = "failed" if error else "done"
    job.output_path = output_path
    job.error = error
    job.finished_at = dt.datetime.utcnow()
    await session.commit()
