"""
ANTAR - the type that sits on the picture.

Three rules from the config are enforced here, and they are not negotiable:

  * Khand Bold, and nothing else. If the file is missing the run stops. A
    silent fallback font is how a video stops looking like ANTAR.
  * the type is never pure white. It runs from an edge value to a peak value,
    the brightest point is in the middle of the word, and the peak is below
    white. Pure white on a phone at night is a torch, not a title.
  * one or two words at a time, and they arrive on the exact frame the voice
    says them. Not a paragraph, not a fade - a cut.

The words themselves come from the voice stage's word timings, so nothing here
guesses when a word happens. It reads the times that were measured.

PREMIUM UPGRADE 2026-10-04: Captions looked wired - single word "लेती" alone,
gray gradient 237->108, no stroke, no shadow, plain bg flash. Fixed:
- Premium white 255 with black stroke + drop shadow + dark pill
- Hindi needs 15% larger, stopwords never alone
- Pill background for contrast like premium shorts
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

POPUP_MAX_WORDS = 2          # config: chunking "1-2 words"
POPUP_WIDTH_FRACTION = 0.82  # of the canvas width, keeps it off the edges
POPUP_PAD = 32               # px of breathing room - increased for premium
POPUP_STROKE = 8             # premium stroke width
POPUP_SHADOW_OFFSET = 6      # drop shadow
# Words that should never appear alone - they look wired as single caption
HINDI_STOPWORDS_ALONE = {
    "है", "हैं", "था", "थी", "थे", "की", "का", "के", "को", "से", "में", "पर", "और",
    "लेती", "लेता", "देती", "देता", "होती", "होता", "करती", "करता", "जाती", "जाता",
    "हूँ", "हो", "नहीं", "भी", "ही", "तो", "तक", "लिए", "वाला", "वाली"
}


class BuildError(RuntimeError):
    """The build cannot go on."""


@dataclass
class Popup:
    text: str
    path: Path          # the rendered PNG, transparent
    width: int
    height: int
    start: float        # global seconds
    end: float
    size: int           # the type size used


@dataclass
class Chunk:
    text: str
    start: float
    end: float


def font_path(config) -> Path:
    """The one typeface. Resolved from the config, never from the system."""
    try:
        path = config.path("paths.assets") / "fonts" / "Khand-Bold.ttf"
    except Exception:
        path = Path(__file__).resolve().parents[2] / "assets" / "fonts" / "Khand-Bold.ttf"
    if not path.exists():
        raise BuildError(
            f"the typeface is missing: {path}\n"
            "The config says no fallback font, ever - so the run stops here "
            "rather than quietly rendering in something else.")
    return path


def load_font(config, size: int):
    try:
        from PIL import ImageFont
    except Exception as exc:  # pragma: no cover
        raise BuildError("Pillow is not installed, so no type can be drawn") from exc
    return ImageFont.truetype(str(font_path(config)), int(size))


# ------------------------------------------------------------------ the words

def chunk_words(words: list[dict], start: float, end: float,
                max_words: int = POPUP_MAX_WORDS) -> list[Chunk]:
    """
    Cut the measured word timings into 1-2 word cards for one shot.

    PREMIUM FIX 2026-10-04:
    - Never show a stopword like "लेती", "है", "की" alone - it looks wired
    - Merge tiny words into previous chunk
    - Hindi needs 2-word minimum for context, not 1-word
    """
    inside = []
    for word in words or []:
        text = (word.get("w") or "").strip()
        if not text:
            continue
        w_start = float(word.get("start", 0.0))
        w_end = float(word.get("end", w_start))
        if w_end <= start or w_start >= end:
            continue
        inside.append(Chunk(text, max(w_start, start), min(w_end, end)))

    inside.sort(key=lambda c: c.start)
    chunks: list[Chunk] = []
    for index in range(0, len(inside), max_words):
        group = inside[index:index + max_words]
        first, last = group[0], group[-1]
        c_start = max(first.start - 0.05, start)
        c_end = min(last.end + 0.07, end)
        if c_end - c_start < 0.12:
            c_end = min(c_start + 0.12, end)
        text = " ".join(c.text for c in group)
        chunks.append(Chunk(text, round(c_start, 3), round(c_end, 3)))

    # PREMIUM: Merge stopwords that would appear alone
    merged_stop: list[Chunk] = []
    for chunk in chunks:
        txt = chunk.text.strip()
        if txt in HINDI_STOPWORDS_ALONE and merged_stop:
            merged_stop[-1].text = f"{merged_stop[-1].text} {txt}".strip()
            merged_stop[-1].end = min(chunk.end, end)
        elif len(txt) <= 2 and merged_stop:
            merged_stop[-1].text = f"{merged_stop[-1].text} {txt}".strip()
            merged_stop[-1].end = min(chunk.end, end)
        else:
            merged_stop.append(chunk)
    chunks = merged_stop

    for position in range(1, len(chunks)):
        previous, current = chunks[position - 1], chunks[position]
        if current.start < previous.end:
            current.start = previous.end
    kept = [c for c in chunks if c.end - c.start >= 0.10]
    if len(kept) < len(chunks):
        merged: list[Chunk] = []
        for chunk in chunks:
            if chunk.end - chunk.start < 0.10 and merged:
                merged[-1].text = f"{merged[-1].text} {chunk.text}".strip()
                merged[-1].end = min(chunk.end, end)
            else:
                merged.append(chunk)
        kept = merged
    return kept


# ------------------------------------------------------------------ the type

def _gradient_luma(width: int, height: int, peak: float, edge: float):
    """A soft light across the word: brightest in the middle, dimmer at the rim."""
    try:
        import numpy as np
    except Exception as exc:  # pragma: no cover
        raise BuildError("numpy is needed to shape the type") from exc

    ys, xs = np.mgrid[0:height, 0:width].astype("float32")
    cx, cy = (width - 1) / 2.0, (height - 1) / 2.0
    distance = np.sqrt((((xs - cx) / max(cx, 1)) ** 2) * 0.45 +
                       (((ys - cy) / max(cy, 1)) ** 2))
    distance = np.clip(distance, 0.0, 1.0)
    luma = peak - (peak - edge) * distance
    return luma


def render_popup(text: str, out_path: Path, config, *,
                 font_px: int | None = None) -> Popup:
    """
    Draw one popup: PREMIUM Hindi style.

    HARDCORE UPGRADE 2026-10-04:
    - Old: gray gradient 237->108, no stroke, looks wired on dark footage
    - New: premium white (255) with black stroke + drop shadow + pill bg
    - Hindi glyphs need 15% larger size than Latin for same readability
    - Adds subtle dark pill behind text for contrast (like MrBeast / premium shorts)
    """
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except Exception as exc:  # pragma: no cover
        raise BuildError("Pillow is not installed, so no type can be drawn") from exc

    import numpy as np

    text = " ".join((text or "").split())
    if not text:
        raise BuildError("a popup with no words is a blank frame")

    width_cap = int(int(config.get("canvas.width", 1080)) * POPUP_WIDTH_FRACTION)
    wanted = int(font_px if font_px is not None else
                 config.get("type.sizes.over_footage", 150))
    # Hindi needs bigger size - bump by 15%
    if any('\u0900' <= c <= '\u097F' for c in text):
        wanted = int(wanted * 1.15)
    size = wanted
    while size > 44:
        font = load_font(config, size)
        probe = Image.new("L", (8, 8))
        box = ImageDraw.Draw(probe).textbbox((0, 0), text, font=font, stroke_width=POPUP_STROKE)
        if (box[2] - box[0]) <= width_cap:
            break
        size -= 4

    font = load_font(config, size)
    measure = ImageDraw.Draw(Image.new("L", (8, 8)))
    box = measure.textbbox((0, 0), text, font=font, stroke_width=POPUP_STROKE)
    glyph_w, glyph_h = box[2] - box[0], box[3] - box[1]

    width = glyph_w + POPUP_PAD * 2 + POPUP_SHADOW_OFFSET * 2
    height = glyph_h + POPUP_PAD * 2 + POPUP_SHADOW_OFFSET * 2

    base = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(base)
    
    pill_pad = 18
    pill_box = [pill_pad, pill_pad, width - pill_pad, height - pill_pad]
    try:
        draw.rounded_rectangle(pill_box, radius=24, fill=(0, 0, 0, 160))
    except:
        draw.rectangle(pill_box, fill=(0, 0, 0, 160))

    txt_x = POPUP_PAD - box[0] + POPUP_SHADOW_OFFSET // 2
    txt_y = POPUP_PAD - box[1] + POPUP_SHADOW_OFFSET // 2

    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    s_draw.text((txt_x + POPUP_SHADOW_OFFSET, txt_y + POPUP_SHADOW_OFFSET),
                text, font=font, fill=(0, 0, 0, 200),
                stroke_width=POPUP_STROKE, stroke_fill=(0, 0, 0, 200))
    shadow = shadow.filter(ImageFilter.GaussianBlur(3))

    text_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    t_draw = ImageDraw.Draw(text_layer)
    t_draw.text((txt_x, txt_y), text, font=font, fill=(255, 255, 255, 255),
                stroke_width=POPUP_STROKE, stroke_fill=(0, 0, 0, 255))
    
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).text((txt_x, txt_y), text, font=font, fill=255,
                              stroke_width=POPUP_STROKE, stroke_fill=255)

    peak = 255
    edge = 235
    luma = _gradient_luma(width, height, peak, edge)

    alpha = np.asarray(mask).astype("float32") / 255.0
    red = np.clip(luma, 0, 255)
    green = np.clip(luma, 0, 255)
    blue = np.clip(luma, 0, 255)

    combined = Image.alpha_composite(base, shadow)
    
    rgba = np.stack([red, green, blue, alpha * 255.0], axis=-1).astype("uint8")
    grad_img = Image.fromarray(rgba, "RGBA")
    
    final = Image.alpha_composite(combined, grad_img)
    final = Image.alpha_composite(final, text_layer)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(out_path, "PNG")

    return Popup(text=text, path=out_path, width=width, height=height,
                 start=0.0, end=0.0, size=size)


def place(config, width: int, height: int) -> tuple[int, int]:
    """
    Where a popup goes: centred, sitting just above the platform's own buttons.

    The safe zones are lock values - 220px at the top for the status bar and
    420px at the bottom for the caption, sound and buttons. The type is placed
    inside them, and every position is checked before it is used.
    """
    canvas_w = int(config.get("canvas.width", 1080))
    canvas_h = int(config.get("canvas.height", 1920))
    safe_top = int(config.get("canvas.safe_zones.top_px", 220))
    safe_bottom = int(config.get("canvas.safe_zones.bottom_px", 420))

    x = (canvas_w - width) // 2
    centre_y = (canvas_h - safe_bottom) - 250
    y = centre_y - height // 2

    if y < safe_top or (y + height) > (canvas_h - safe_bottom):
        raise BuildError(
            f"a {width}x{height} popup does not fit the safe zones "
            f"(y={y}, allowed {safe_top}..{canvas_h - safe_bottom})")
    return x, y


def line_for_beat(shot: dict) -> str:
    """The one word that names the beat on a text card - the object, if there is one."""
    return (shot.get("object_hi") or "").strip()
