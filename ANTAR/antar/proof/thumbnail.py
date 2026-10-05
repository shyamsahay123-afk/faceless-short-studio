"""
ANTAR - the real thumbnail.

The Phase 5 build is 1080x1920 portrait - that is what plays in the Shorts
feed. The thumbnail YouTube shows beside a Short, in the upload form, in the
search result, in the comments panel - is a wider image: the platform itself
expects 1280x720 and refuses to crop a portrait still.

This file does the work the auto picker promises:

  1. CUT - take the brightest compliant second the details stage chose, save
     it as a real image at the video's own size (1080x1920), full colour, not
     a feed-tile crop, not a posterised shell. This file is what
     `thumbnail_path` in the details file points at.

  2. COMPOSE - make a 1280x720 landscape thumbnail for the upload form, the way
     the platform's own docs describe: full-bleed vertical frame, the chosen
     word in Khand Bold at the lower-right, in front of the footage. The
     result is what an operator uploads.

  3. CHECK - measure both files with `vision._measure`, the same helper the
     check suite grades thumbnails with, so the panel, the check, and this
     stage all read the same number.

The picked second never comes from the pipeline assuming - it comes from the
details file, and a manual override from the panel still wins, because the
panel writes that back into the details file before this stage runs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..checks import vision
from ..vault import find_ffmpeg


LANDSCAPE = (1280, 720)         # the platform's expected thumbnail size
SAFE_W = 1180                   # the 50px safe inset the platform hides
SAFE_H = 660


class ThumbError(RuntimeError):
    """A real thumbnail could not be made, and here is why."""


def make_real_thumbnail(config, render_id: str, details_path: Path,
                        *, video_path: Path | None = None) -> dict:
    """
    Cut the chosen frame and compose the landscape thumbnail.

    Reads the chosen second from the details file (which may have been
    overridden by the panel's manual pick), writes two files, and returns a
    record the panel and the report both read.
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise ThumbError("no ffmpeg available - run INSTALL.bat")

    if not details_path.exists():
        raise ThumbError(
            f"there are no details for {render_id} yet - run: python run.py details")

    details = json.loads(details_path.read_text(encoding="utf-8"))
    thumb_meta = details.get("thumbnail") or {}
    second = float(thumb_meta.get("at") or 0.0)
    if second < 0:
        second = 0.0

    video = video_path or (config.path("paths.output") / "video" / f"{render_id}.mp4")
    if not video.exists():
        raise ThumbError(
            f"there is no {render_id}.mp4 to take a frame from. Videos are "
            f"delivered in ANTAR_VIDEOS.zip and deleted from the workshop, so "
            f"the real thumbnail cannot be cut until one is present again.")

    folder = config.path("paths.output") / "thumbs"
    folder.mkdir(parents=True, exist_ok=True)

    full = folder / f"{render_id}_real.jpg"
    landscape = folder / f"{render_id}_landscape.jpg"

    _cut_full(ffmpeg, video, second, full, config)
    mean, black, pure = vision._measure(full)
    contrast = vision.contrast(full)
    low = float(config.get("thresholds.thumbnail_brightness_min", 35))
    high = float(config.get("thresholds.thumbnail_brightness_max", 45))
    in_band = low <= mean <= high

    title = details.get("title_hi", "")
    _compose_landscape(full, landscape, title, config)

    landscape_mean, _, _ = vision._measure(landscape)

    record = {
        "render_id": render_id,
        "picked_second": second,
        "full": str(full),
        "landscape": str(landscape),
        "full": str(full),
        "landscape_mean": round(landscape_mean, 1),
        "full_brightness": round(mean, 1),
        "full_contrast": round(contrast, 1),
        "black_pct": round(black, 1),
        "band": [low, high],
        "in_band": in_band,
        "size": LANDSCAPE,
        "manual_override": bool(details.get("thumbnail_manual") or details.get("edited_by_hand")),
        "note": (f"inside the locked band {low:.0f}-{high:.0f}" if in_band else
                 f"outside the locked band {low:.0f}-{high:.0f} - the check suite "
                 f"will flag this frame, so the operator can re-pick in the panel"),
    }
    return record


def _cut_full(ffmpeg: str, video: Path, second: float, out: Path, config) -> None:
    """
    One frame at the video's own size.

    The vertical video stays vertical here. The landscape version comes from
    a separate compose step. Cutting full first means the feed tile, the
    landscape thumbnail, and the operator's preview are all derived from the
    same still.
    """
    width = int(config.get("canvas.width", 1080))
    height = int(config.get("canvas.height", 1920))
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-v", "error",
         "-ss", f"{second:.3f}", "-i", str(video),
         "-vf", (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                 f"crop={width}:{height}"),
         "-frames:v", "1", "-q:v", "3", "-y", str(out)],
        capture_output=True, text=True)
    if result.returncode or not out.exists():
        raise ThumbError(f"the frame could not be cut: {result.stderr.strip()[:200]}")


def _compose_landscape(full: Path, landscape: Path, title: str, config) -> None:
    """
    The 1280x720 landscape thumbnail, in two layers:

      - the bottom layer: the vertical frame, scaled to fit the height, the
        sides in the locked near-black so the type sits on a safe surface;
      - the top layer: the title in Khand Bold at the lower-right, inside the
        safe zone, with a soft dark plate behind it so the same word is
        legible on a busy frame and a flat one.

    The platform says 1280x720 is the canonical thumbnail size, so that is
    what this writes.
    """
    font_path = config.path("paths.assets") / "fonts" / "Khand-Bold.ttf"
    try:
        font = ImageFont.truetype(str(font_path), size=88)
    except OSError:
        font = ImageFont.load_default()

    with Image.open(full).convert("RGB") as source:
        canvas = Image.new("RGB", LANDSCAPE, (11, 11, 15))
        source_ratio = source.width / source.height
        target_ratio = LANDSCAPE[0] / LANDSCAPE[1]
        if source_ratio > target_ratio:
            new_height = LANDSCAPE[1]
            new_width = int(round(new_height * source_ratio))
        else:
            new_width = LANDSCAPE[0]
            new_height = int(round(new_width / source_ratio))
        scaled = source.resize((new_width, new_height), Image.LANCZOS)
        offset = ((LANDSCAPE[0] - new_width) // 2, (LANDSCAPE[1] - new_height) // 2)
        canvas.paste(scaled, offset)

        draw = ImageDraw.Draw(canvas)
        if title:
            _draw_title(draw, canvas, title, font)

    canvas.save(landscape, quality=92, optimize=True)


def _draw_title(draw: ImageDraw.ImageDraw, canvas: Image.Image, title: str,
                font: ImageFont.FreeTypeFont) -> None:
    """
    Title in Khand, lower-right, with a dark plate behind it for legibility.

    The title is split onto lines that fit within the safe width. The plate
    sits behind the type, not over the whole frame, so the footage still
    shows through - this is a thumbnail of the video, not of the text.
    """
    safe_left = (LANDSCAPE[0] - SAFE_W) // 2
    safe_right = LANDSCAPE[0] - safe_left
    safe_bottom = LANDSCAPE[1] - 50

    lines: list[str] = []
    words = title.split()
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] > SAFE_W - 40:
            if current:
                lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)

    line_height = 90
    block_height = line_height * len(lines) + 36
    top = safe_bottom - block_height

    plate_left = safe_left + 30
    plate_right = safe_right - 30
    plate_bottom = safe_bottom - 10
    plate_top = top - 18
    plate_box = (plate_left, plate_top, plate_right, plate_bottom)
    draw.rectangle(plate_box, fill=(8, 8, 12, 230))

    for index, line in enumerate(lines):
        y = plate_top + 18 + index * line_height
        bbox = draw.textbbox((0, 0), line, font=font)
        width = bbox[2] - bbox[0]
        x = plate_right - width - 30
        # a soft warm glow underneath the type, so it reads on a dark frame
        for offset, alpha in ((2, 60), (1, 100), (0, 200)):
            draw.text((x - offset, y), line, font=font, fill=(0, 0, 0, alpha))
            draw.text((x + offset, y), line, font=font, fill=(0, 0, 0, alpha))
        draw.text((x, y), line, font=font, fill=(232, 230, 225))


def fallback_landscape(full: Path, landscape: Path, config) -> None:
    """
    A landscape thumb built from the full-frame, no title - the upload form
    must always have something legible to show.

    Used when the title is empty (the details stage has not run yet) or when
    Khand is missing. The platform's preview still works.
    """
    with Image.open(full).convert("RGB") as source:
        scaled = source.copy()
        scaled.thumbnail(LANDSCAPE, Image.LANCZOS)
        canvas = Image.new("RGB", LANDSCAPE, (11, 11, 15))
        offset = ((LANDSCAPE[0] - scaled.width) // 2,
                  (LANDSCAPE[1] - scaled.height) // 2)
        canvas.paste(scaled, offset)
    canvas.save(landscape, quality=90, optimize=True)
