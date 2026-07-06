"""
High-level media processor: takes a Template DB row + input file, decides
photo vs. video, and calls the correct watermark engine. Used identically by
the Telegram bot handlers, the webapp API, and the channel auto-watermark
listener — single source of truth for "how do we apply a template".
"""
from __future__ import annotations

import uuid
from pathlib import Path

from bot.config import OUTPUT_DIR
from bot.database.models import Template, Tail
from bot.utils.image_watermark import apply_watermark_to_image
from bot.utils.video_watermark import apply_photo_watermark_to_video, apply_text_watermark_to_video

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}


def detect_media_type(path: str | Path) -> str:
    ext = Path(path).suffix.lower()
    if ext in IMAGE_EXTS:
        return "photo"
    if ext in VIDEO_EXTS:
        return "video"
    raise ValueError(f"Unsupported file type: {ext}")


def _new_output_path(suffix: str) -> Path:
    return OUTPUT_DIR / f"{uuid.uuid4().hex}{suffix}"


def process_file(input_path: str | Path, template: Template, tail: Tail | None = None) -> Path:
    """
    Apply `template`'s watermark configuration to `input_path`.
    Returns the path to the produced output file.
    """
    input_path = Path(input_path)
    media_type = detect_media_type(input_path)

    if media_type == "photo":
        out_path = _new_output_path(input_path.suffix if input_path.suffix.lower() != ".webp" else ".png")
        return apply_watermark_to_image(
            input_path, out_path,
            kind=template.kind,
            watermark_image_path=template.image_path,
            text_content=template.text_content,
            font_family=template.font_family,
            font_size=template.font_size,
            font_color=template.font_color,
            position=template.position,
            offset_x_pct=template.offset_x_pct,
            offset_y_pct=template.offset_y_pct,
            width_pct=template.width_pct,
            opacity_pct=template.opacity_pct,
            rotation_deg=template.rotation_deg,
        )

    # video
    out_path = _new_output_path(".mp4")
    tail_path = tail.file_path if tail else None

    if template.kind == "photo":
        return apply_photo_watermark_to_video(
            input_path, out_path, template.image_path,
            position=template.position,
            offset_x_pct=template.offset_x_pct,
            offset_y_pct=template.offset_y_pct,
            width_pct=template.width_pct,
            opacity_pct=template.opacity_pct,
            screen_movement=template.screen_movement,
            tail_path=tail_path,
        )
    else:
        return apply_text_watermark_to_video(
            input_path, out_path,
            text_content=template.text_content,
            font_color=template.font_color,
            position=template.position,
            offset_x_pct=template.offset_x_pct,
            offset_y_pct=template.offset_y_pct,
            opacity_pct=template.opacity_pct,
            screen_movement=template.screen_movement,
            tail_path=tail_path,
        )
