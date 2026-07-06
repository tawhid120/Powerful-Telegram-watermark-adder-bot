"""
Image watermarking engine.

Supports:
  - Photo (logo/PNG with transparency) watermarks
  - Text watermarks with custom font/size/color
  - 9 anchored positions + random + fill (tiled) placement
  - Offset (%), width (%), opacity (%), rotation (degrees)

All percentage values are relative to the base image dimensions, matching
the sliders shown in the reference UI (Horizontal offset %, Vertical offset %,
Width %, Opacity %, Rotation angle °).
"""
from __future__ import annotations

import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance


DEFAULT_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _load_font(size: int, font_family: str | None = None) -> ImageFont.FreeTypeFont:
    candidates = []
    if font_family and font_family != "default":
        candidates.append(font_family)
    candidates.extend(DEFAULT_FONT_CANDIDATES)
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _hex_to_rgba(hex_color: str, opacity_pct: float) -> tuple[int, int, int, int]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    a = max(0, min(255, round(255 * opacity_pct / 100)))
    return r, g, b, a


def _build_text_layer(text: str, font_family: str, font_size: int, color_hex: str,
                       opacity_pct: float) -> Image.Image:
    font = _load_font(font_size, font_family)
    dummy = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = max(4, font_size // 6)
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rgba = _hex_to_rgba(color_hex, opacity_pct)
    d.text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=rgba)
    return layer


def _scale_layer_to_width(layer: Image.Image, target_w: int) -> Image.Image:
    target_w = max(1, target_w)
    ratio = target_w / layer.width
    target_h = max(1, round(layer.height * ratio))
    return layer.resize((target_w, target_h), Image.LANCZOS)


def _apply_opacity_to_rgba(layer: Image.Image, opacity_pct: float) -> Image.Image:
    if opacity_pct >= 100:
        return layer
    r, g, b, a = layer.split()
    a = a.point(lambda p: int(p * opacity_pct / 100))
    return Image.merge("RGBA", (r, g, b, a))


def _anchor_position(base_size: tuple[int, int], layer_size: tuple[int, int],
                      position: str, offset_x_pct: float, offset_y_pct: float) -> tuple[int, int]:
    bw, bh = base_size
    lw, lh = layer_size
    ox = round(bw * offset_x_pct / 100)
    oy = round(bh * offset_y_pct / 100)

    positions = {
        "top-left": (ox, oy),
        "top-center": ((bw - lw) // 2, oy),
        "top-right": (bw - lw - ox, oy),
        "middle-left": (ox, (bh - lh) // 2),
        "center": ((bw - lw) // 2, (bh - lh) // 2),
        "middle-right": (bw - lw - ox, (bh - lh) // 2),
        "bottom-left": (ox, bh - lh - oy),
        "bottom-center": ((bw - lw) // 2, bh - lh - oy),
        "bottom-right": (bw - lw - ox, bh - lh - oy),
    }
    if position == "random":
        x = random.randint(0, max(0, bw - lw))
        y = random.randint(0, max(0, bh - lh))
        return x, y
    return positions.get(position, positions["bottom-right"])


def apply_watermark_to_image(
    base_path: str | Path,
    output_path: str | Path,
    *,
    kind: str,  # "text" | "photo"
    watermark_image_path: str | None = None,
    text_content: str | None = None,
    font_family: str = "default",
    font_size: int = 32,
    font_color: str = "#FFFFFF",
    position: str = "bottom-right",
    offset_x_pct: float = 5.0,
    offset_y_pct: float = 5.0,
    width_pct: float = 25.0,
    opacity_pct: float = 100.0,
    rotation_deg: float = 0.0,
) -> Path:
    """Apply a single watermark configuration to a still image and save the result."""
    base = Image.open(base_path).convert("RGBA")

    if kind == "photo":
        if not watermark_image_path:
            raise ValueError("watermark_image_path required for kind='photo'")
        layer = Image.open(watermark_image_path).convert("RGBA")
    else:
        if not text_content:
            raise ValueError("text_content required for kind='text'")
        layer = _build_text_layer(text_content, font_family, font_size, font_color, 100.0)

    target_w = round(base.width * width_pct / 100)
    layer = _scale_layer_to_width(layer, target_w)

    if rotation_deg:
        layer = layer.rotate(rotation_deg, expand=True, resample=Image.BICUBIC)

    layer = _apply_opacity_to_rgba(layer, opacity_pct)

    if position == "fill":
        # Tile the watermark across the whole image (repeating pattern)
        tile_canvas = Image.new("RGBA", base.size, (0, 0, 0, 0))
        step_x = layer.width + round(base.width * offset_x_pct / 100)
        step_y = layer.height + round(base.height * offset_y_pct / 100)
        step_x, step_y = max(step_x, 1), max(step_y, 1)
        for y in range(0, base.height, step_y):
            for x in range(0, base.width, step_x):
                tile_canvas.alpha_composite(layer, (x, y))
        result = Image.alpha_composite(base, tile_canvas)
    else:
        x, y = _anchor_position(base.size, layer.size, position, offset_x_pct, offset_y_pct)
        result = base.copy()
        result.alpha_composite(layer, (x, y))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() in (".jpg", ".jpeg"):
        result = result.convert("RGB")
    result.save(output_path)
    return output_path
