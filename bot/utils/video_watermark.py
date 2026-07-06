"""
Video watermarking engine, built on top of ffmpeg (via subprocess for full control
over overlay filters — ffmpeg-python's high level API is too limited for the
animated 'screen movement' and 'fill' modes we need).

Requires ffmpeg to be installed on the host system:
    sudo apt-get install ffmpeg

Supports:
  - Photo (PNG) watermark overlay on video
  - Text watermark overlay (drawtext) on video
  - Static anchored position (9 positions) + fill (tiled)
  - "Screen movement" mode: watermark drifts/bounces across the frame over time
    (like a DVD-logo bounce), matching the reference UI's "Screen movement" toggle
  - Optional "video tail": append a short clip/image at the end of the output
"""
from __future__ import annotations

import subprocess
import shlex
from pathlib import Path


def _position_expr(position: str, ox_pct: float, oy_pct: float) -> tuple[str, str]:
    """Return ffmpeg overlay filter x/y expressions for a static anchor position."""
    ox = f"(main_w*{ox_pct/100})"
    oy = f"(main_h*{oy_pct/100})"
    table = {
        "top-left": (ox, oy),
        "top-center": ("(main_w-overlay_w)/2", oy),
        "top-right": (f"(main_w-overlay_w-{ox})", oy),
        "middle-left": (ox, "(main_h-overlay_h)/2"),
        "center": ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2"),
        "middle-right": (f"(main_w-overlay_w-{ox})", "(main_h-overlay_h)/2"),
        "bottom-left": (ox, f"(main_h-overlay_h-{oy})"),
        "bottom-center": ("(main_w-overlay_w)/2", f"(main_h-overlay_h-{oy})"),
        "bottom-right": (f"(main_w-overlay_w-{ox})", f"(main_h-overlay_h-{oy})"),
    }
    return table.get(position, table["bottom-right"])


def _movement_expr() -> tuple[str, str]:
    """
    Bouncing 'DVD logo' style motion expression, driven by ffmpeg's `t` (time) variable.
    Uses a triangular wave so the watermark bounces smoothly between edges.
    """
    x = "abs(mod(t*80,(2*(main_w-overlay_w)))-(main_w-overlay_w))"
    y = "abs(mod(t*55,(2*(main_h-overlay_h)))-(main_h-overlay_h))"
    return x, y


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.decode(errors='ignore')[-2000:]}")


def apply_photo_watermark_to_video(
    input_path: str | Path,
    output_path: str | Path,
    watermark_image_path: str | Path,
    *,
    position: str = "bottom-right",
    offset_x_pct: float = 5.0,
    offset_y_pct: float = 5.0,
    width_pct: float = 25.0,
    opacity_pct: float = 100.0,
    screen_movement: bool = False,
    tail_path: str | Path | None = None,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    opacity = max(0.0, min(1.0, opacity_pct / 100))

    # Scale watermark relative to main video width, then adjust opacity via colorchannelmixer.
    scale_expr = f"scale=iw*{width_pct/100}*(main_w/iw):-1"
    # simpler & robust: scale watermark to width_pct of MAIN width using overlay's own coordinates
    filter_complex = (
        f"[1:v]format=rgba,scale=W*{width_pct/100}:-1,"
        f"colorchannelmixer=aa={opacity}[wm];"
    )

    if screen_movement:
        x_expr, y_expr = _movement_expr()
    else:
        x_expr, y_expr = _position_expr(position, offset_x_pct, offset_y_pct)

    filter_complex += f"[0:v][wm]overlay=x='{x_expr}':y='{y_expr}':eval=frame[outv]"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-i", str(watermark_image_path),
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "copy",
        str(output_path if not tail_path else _tmp_path(output_path)),
    ]
    _run(cmd)

    if tail_path:
        _append_tail(_tmp_path(output_path), tail_path, output_path)
        _tmp_path(output_path).unlink(missing_ok=True)

    return output_path


def apply_text_watermark_to_video(
    input_path: str | Path,
    output_path: str | Path,
    *,
    text_content: str,
    font_color: str = "#FFFFFF",
    font_size_pct: float = 4.0,  # font size as % of video height, for resolution independence
    position: str = "bottom-right",
    offset_x_pct: float = 5.0,
    offset_y_pct: float = 5.0,
    opacity_pct: float = 100.0,
    screen_movement: bool = False,
    tail_path: str | Path | None = None,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    opacity = max(0.0, min(1.0, opacity_pct / 100))
    color = font_color.lstrip("#")
    escaped_text = text_content.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    font_size_expr = f"h*{font_size_pct/100}"

    if screen_movement:
        x_expr, y_expr = _movement_expr()
        x_expr, y_expr = x_expr.replace("overlay_w", "text_w").replace("overlay_h", "text_h"), \
            y_expr.replace("overlay_w", "text_w").replace("overlay_h", "text_h")
    else:
        x_expr, y_expr = _position_expr(position, offset_x_pct, offset_y_pct)
        x_expr = x_expr.replace("overlay_w", "text_w").replace("overlay_h", "text_h").replace("main_w", "w").replace("main_h", "h")
        y_expr = y_expr.replace("overlay_w", "text_w").replace("overlay_h", "text_h").replace("main_w", "w").replace("main_h", "h")

    drawtext = (
        f"drawtext=text='{escaped_text}':fontcolor={color}@{opacity}:"
        f"fontsize={font_size_expr}:x='{x_expr}':y='{y_expr}':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", drawtext,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "copy",
        str(output_path if not tail_path else _tmp_path(output_path)),
    ]
    _run(cmd)

    if tail_path:
        _append_tail(_tmp_path(output_path), tail_path, output_path)
        _tmp_path(output_path).unlink(missing_ok=True)

    return output_path


def _tmp_path(path: Path) -> Path:
    return path.with_suffix(".pretail" + path.suffix)


def _append_tail(main_path: Path, tail_path: str | Path, output_path: Path) -> None:
    """Concatenate a short 'tail' clip/image after the watermarked video using ffmpeg concat demuxer."""
    tail_path = Path(tail_path)
    list_file = output_path.with_suffix(".concat.txt")

    # If tail is an image, first convert to a short video matching main video's resolution/fps.
    if tail_path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        tail_video = output_path.with_suffix(".tailvid.mp4")
        probe_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate",
            "-of", "csv=p=0", str(main_path),
        ]
        proc = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        w, h, fps = proc.stdout.decode().strip().split(",")
        fps_val = fps.split("/")[0]
        _run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(tail_path), "-t", "3",
            "-vf", f"scale={w}:{h},format=yuv420p", "-r", fps_val,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(tail_video),
        ])
        tail_path = tail_video

    list_file.write_text(f"file '{main_path.resolve()}'\nfile '{Path(tail_path).resolve()}'\n")
    _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", str(output_path),
    ])
    list_file.unlink(missing_ok=True)
