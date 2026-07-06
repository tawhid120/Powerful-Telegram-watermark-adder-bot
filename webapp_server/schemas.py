from __future__ import annotations
from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    init_data: str


class AuthResponse(BaseModel):
    token: str
    user_id: int
    plan: str
    template_limit: int
    channel_limit: int


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    kind: str = Field(pattern="^(text|photo)$")
    text_content: str | None = None
    font_family: str = "default"
    font_size: int = 32
    font_color: str = "#FFFFFF"
    position: str = "bottom-right"
    offset_x_pct: float = 5.0
    offset_y_pct: float = 5.0
    width_pct: float = 25.0
    opacity_pct: float = 100.0
    rotation_deg: float = 0.0
    screen_movement: bool = False


class TemplateOut(TemplateIn):
    id: int
    image_path: str | None = None
    is_default: bool = False

    class Config:
        from_attributes = True


class ChannelOut(BaseModel):
    id: int
    chat_id: int
    title: str
    template_id: int | None
    tail_id: int | None
    is_active: bool

    class Config:
        from_attributes = True


class ChannelIn(BaseModel):
    template_id: int | None = None
    tail_id: int | None = None
    is_active: bool = True


class ProfileOut(BaseModel):
    id: int
    username: str | None
    first_name: str | None
    plan: str
    daily_bytes_used: int
    daily_limit_bytes: int
    template_count: int
    template_limit: int
    channel_count: int
    channel_limit: int
