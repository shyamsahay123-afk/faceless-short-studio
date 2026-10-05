"""
ANTAR - the text card.

When no clip comes back for a beat, the beat does not get a placeholder, a
loading screen or a gap. It gets a card: the word, alone, on a lifted black,
lit from behind.

The rules it keeps:

  * house colour, never #000000. The config bans pure black everywhere and a
    card is not an exception.
  * ONE bright element, and it is the word.
  * the word is never pure white either. #E9E9EF at most - pure white on a
    phone at night is a torch.
  * everything inside the safe zones, so the platform's own buttons never sit
    on top of the word.
  * brightness between 35 and 45 on the 0-255 scale, which is the same band
    every other frame in the video has to sit in. A card that is darker than
    the footage around it reads as a mistake.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .. import log

CARD_WORD_MAX = (233, 233, 239)      # never pure white


class CardError(RuntimeError):
    """The card could not be drawn."""


@dataclass
class Card:
    path: Path
    word: str
    brightness: float
    font_px: int


def _rgb(value: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    value = (value or "").strip().lstrip("#")
    if len(value) != 6:
        return fallback
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return fallback


def _pil():
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
    except Exception as exc:  # pragma: no cover - only when Pillow is absent
        raise CardError(
            "Pillow is not installed, so a text card cannot be drawn. "
            "Run: pip install pillow") from exc
    return Image, ImageDraw, ImageFilter, ImageFont


def _fit(draw, word: str, font_loader, width: int, height: int,
         top: int, bottom: int) -> tuple[object, int]:
    """The largest type size at which the word still fits the safe zone."""
    size = 320
    while size > 40:
        font = font_loader(size)
        box = draw.textbbox((0, 0), word, font=font)
        if (box[2] - box[0]) <= width and (box[3] - box[1]) <= (bottom - top):
            return font, size
        size -= 8
    return font_loader(40), 40


def _draw(word: str, out_path: Path, config, brighten: float, font_path: Path) -> int:
    """Draw one card at a given lift. Returns the type size used.
    
    PREMIUM UPGRADE 2026-10-04: Old card was plain #12121A with single word,
    looked like loading screen. New: cinematic gradient + texture + premium typography.
    """
    Image, ImageDraw, ImageFilter, ImageFont = _pil()

    width = int(config.get("canvas.width", 1080))
    height = int(config.get("canvas.height", 1920))
    safe_top = int(config.get("canvas.safe_zones.top_px", 220))
    safe_bottom = int(config.get("canvas.safe_zones.bottom_px", 420))
    base = _rgb(config.get("canvas.card_colour", "#12121A"), (18, 18, 26))

    def loader(size: int):
        return ImageFont.truetype(str(font_path), size)

    image = Image.new("RGB", (width, height), base)
    draw = ImageDraw.Draw(image)

    # PREMIUM: cinematic vertical gradient + subtle vignette, not flat
    for y in range(height):
        # Dark at edges, lighter in middle - cinematic
        mid = height // 2
        dist = abs(y - mid) / (height / 2)
        lift = int(brighten * (0.5 + 0.5 * (1 - dist)) + 8 * (1 - dist))
        # Add slight blue tint in middle for premium feel
        b_extra = int(6 * (1 - dist))
        draw.line([(0, y), (width, y)],
                  fill=(base[0] + lift, base[1] + lift, base[2] + lift + b_extra))

    # Vignette - darker at corners
    vignette = Image.new("L", (width, height), 0)
    v_draw = ImageDraw.Draw(vignette)
    for i in range(5):
        alpha = int(40 - i * 8)
        v_draw.rectangle([i*30, i*30, width - i*30, height - i*30], outline=alpha, width=30)
    vignette = vignette.filter(ImageFilter.GaussianBlur(80))
    image = Image.composite(Image.new("RGB", (width, height), (8, 8, 12)), image, vignette)
    draw = ImageDraw.Draw(image)

    # the one bright element: a soft light behind the word - bigger, premium
    glow = Image.new("L", (width, height), 0)
    gdraw = ImageDraw.Draw(glow)
    centre_y = (safe_top + (height - safe_bottom)) // 2
    radius = int(width * 0.75)  # bigger glow
    gdraw.ellipse([width // 2 - radius, centre_y - radius // 2,
                   width // 2 + radius, centre_y + radius // 2], fill=110)
    glow = glow.filter(ImageFilter.GaussianBlur(radius // 2))
    image = Image.composite(Image.new("RGB", (width, height), (52, 54, 72)),
                            image, glow)
    draw = ImageDraw.Draw(image)

    usable_w = int(width * 0.80)
    usable_top = centre_y - int((height - safe_top - safe_bottom) * 0.30)
    usable_bottom = centre_y + int((height - safe_top - safe_bottom) * 0.30)

    font, size = _fit(draw, word, loader, usable_w, height, usable_top, usable_bottom)
    box = draw.textbbox((0, 0), word, font=font)
    text_w, text_h = box[2] - box[0], box[3] - box[1]
    x = (width - text_w) // 2 - box[0]
    y = centre_y - text_h // 2 - box[1]

    # Premium: double line above word, with glow
    rule_y = y + box[1] - int(size * 0.32)
    # Outer glow for rule
    draw.rectangle([(width // 2 - text_w // 2 - 10, rule_y - 1),
                    (width // 2 + text_w // 2 + 10, rule_y + 4)], fill=(80, 82, 100))
    draw.rectangle([(width // 2 - text_w // 3, rule_y),
                    (width // 2 + text_w // 3, rule_y + 2)], fill=(180, 182, 200))
    # Second thin line
    draw.rectangle([(width // 2 - text_w // 4, rule_y + 8),
                    (width // 2 + text_w // 4, rule_y + 9)], fill=(120, 122, 140))

    # Premium text: white with subtle shadow
    # Shadow
    draw.text((x+4, y+4), word, font=font, fill=(0, 0, 0, 180))
    draw.text((x, y), word, font=font, fill=CARD_WORD_MAX)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, "PNG")
    return size


def build_card(word: str, out_path: Path, config, *,
               target_brightness: float | None = None) -> Card:
    """
    Draw one card, at the brightness the frame band asks for.

    The lift is SOLVED FOR, not guessed. The card is drawn once flat, its
    average luminance is measured, the slope of luminance against lift is
    measured, and the lift that lands the card in the middle of the band is
    worked out from those two numbers. Different words cover different amounts
    of the frame, so a fixed lift put a two-word card at 44 and a three-word
    card at 47 - both outside the 35-45 band the footage has to sit in.

    Same idea as loudnorm in the audio: measure the thing, then correct it.
    """
    word = (word or "").strip()
    if not word:
        raise CardError("a card needs a word - an empty card is a black frame")

    font_path = Path(config.path("paths.assets")) / "fonts" / "Khand-Bold.ttf"
    if not font_path.exists():
        raise CardError(f"the typeface is missing: {font_path}")

    band = config.get("picture.card.brightness_band", [35, 45])
    target = float(target_brightness if target_brightness is not None
                   else (float(band[0]) + float(band[1])) / 2)

    probe_path = Path(out_path)
    _draw(word, probe_path, config, 0.0, font_path)
    flat = card_brightness(probe_path)
    _draw(word, probe_path, config, 26.0, font_path)
    lifted = card_brightness(probe_path)

    slope = (lifted - flat) / 26.0
    if slope <= 0.01:
        lift = 26.0
    else:
        lift = max(0.0, min(90.0, (target - flat) / slope))

    size = _draw(word, probe_path, config, lift, font_path)
    measured = card_brightness(probe_path)

    # one more correction if the first solve was off, then it is reported as it is
    if abs(measured - target) > 1.5 and slope > 0.01:
        lift = max(0.0, min(90.0, lift + (target - measured) / slope))
        size = _draw(word, probe_path, config, lift, font_path)
        measured = card_brightness(probe_path)

    return Card(path=probe_path, word=word, brightness=measured, font_px=size)


def card_brightness(path: Path) -> float:
    """
    The card's average luminance, 0-255, computed from the file it just wrote.

    Not assumed from the colours that were asked for. The band is 35-45 and
    this is the number that decides whether the card is in it.
    """
    Image, _, _, _ = _pil()
    with Image.open(path) as image:
        grey = image.convert("L")
        histogram = grey.histogram()
    total = sum(histogram)
    if not total:
        return 0.0
    return sum(index * count for index, count in enumerate(histogram)) / total


def frame_black_pct(path: Path, black_level: int = 16) -> float:
    """
    How much of a frame is black, 0-100.

    The rule this feeds is "no frame mostly black" and the number it is judged
    against - 55 - is a blocking threshold already in the config. A pixel
    counts as black below 16 of 255. Read from the file, never assumed.
    """
    Image, _, _, _ = _pil()
    with Image.open(path) as image:
        grey = image.convert("L")
        histogram = grey.histogram()
    total = sum(histogram)
    if not total:
        return 100.0
    return 100.0 * sum(histogram[:black_level]) / total
