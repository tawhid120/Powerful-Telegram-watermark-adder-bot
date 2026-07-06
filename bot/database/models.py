"""
Database models for WMark Bot.
Uses SQLAlchemy 2.0 async ORM with SQLite (swap DATABASE_URL for Postgres/MySQL in production).
"""
from __future__ import annotations

import datetime as dt
from sqlalchemy import (
    BigInteger, String, Integer, Float, Boolean, ForeignKey, DateTime, JSON, Text
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # telegram user id
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    plan: Mapped[str] = mapped_column(String(16), default="free")
    plan_expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    daily_bytes_used: Mapped[int] = mapped_column(BigInteger, default=0)
    daily_reset_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    default_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("templates.id", use_alter=True), nullable=True
    )
    default_tail_id: Mapped[int | None] = mapped_column(
        ForeignKey("tails.id", use_alter=True), nullable=True
    )
    referred_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    templates: Mapped[list["Template"]] = relationship(
        "Template", back_populates="owner", foreign_keys="Template.owner_id", cascade="all, delete-orphan"
    )
    channels: Mapped[list["Channel"]] = relationship(
        "Channel", back_populates="owner", cascade="all, delete-orphan"
    )
    tails: Mapped[list["Tail"]] = relationship(
        "Tail", back_populates="owner", foreign_keys="Tail.owner_id", cascade="all, delete-orphan"
    )


class Template(Base):
    """A saved watermark configuration (text or photo/logo based)."""
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))  # "text" | "photo"

    # For photo watermark
    image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # For text watermark
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    font_family: Mapped[str] = mapped_column(String(64), default="default")
    font_size: Mapped[int] = mapped_column(Integer, default=32)
    font_color: Mapped[str] = mapped_column(String(16), default="#FFFFFF")

    # Shared placement params
    position: Mapped[str] = mapped_column(String(16), default="bottom-right")
    offset_x_pct: Mapped[float] = mapped_column(Float, default=5.0)
    offset_y_pct: Mapped[float] = mapped_column(Float, default=5.0)
    width_pct: Mapped[float] = mapped_column(Float, default=25.0)
    opacity_pct: Mapped[float] = mapped_column(Float, default=100.0)
    rotation_deg: Mapped[float] = mapped_column(Float, default=0.0)
    screen_movement: Mapped[bool] = mapped_column(Boolean, default=False)  # animate across video frames

    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    owner: Mapped["User"] = relationship("User", back_populates="templates", foreign_keys=[owner_id])


class Tail(Base):
    """A short video/image clip appended to the end of processed videos ('video tail')."""
    __tablename__ = "tails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(64))
    file_path: Mapped[str] = mapped_column(String(512))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    owner: Mapped["User"] = relationship("User", back_populates="tails", foreign_keys=[owner_id])


class Channel(Base):
    """A channel where the bot auto-applies a watermark template to all new posts."""
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(128))
    template_id: Mapped[int | None] = mapped_column(ForeignKey("templates.id"), nullable=True)
    tail_id: Mapped[int | None] = mapped_column(ForeignKey("tails.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    owner: Mapped["User"] = relationship("User", back_populates="channels")


class Job(Base):
    """A single watermarking job (one file processed), for history/analytics/rate-limiting."""
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    template_id: Mapped[int | None] = mapped_column(ForeignKey("templates.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="bot")  # "bot" | "webapp" | "channel"
    media_type: Mapped[str] = mapped_column(String(16))  # "photo" | "video"
    input_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    output_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|processing|done|failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
