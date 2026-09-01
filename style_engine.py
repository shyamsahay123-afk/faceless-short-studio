# ==============================================================================
# STYLE ENGINE — ELITE FACELESS SHORTS COMPOSITION SYSTEM
# Layers: animated style backgrounds, stacked hook text, beat text,
# curiosity/stat/before-after cards, arrows, SFX synthesis, frame grading.
# 100% code-generated. No asset downloads. Cross-version MoviePy 1.x/2.x safe.
# ==============================================================================
import os
import re
import math
import zlib
import random
import struct
import datetime
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ACCENTS = {
    "yellow":  (255, 215, 0),
    "green":   (0, 230, 118),
    "cyan":    (0, 229, 255),
    "red":     (255, 60, 60),
    "magenta": (216, 150, 255),
    "orange":  (255, 149, 0),
    "gold":    (212, 175, 55),  # cinematic mystery (reference #3 palette)
}

WIDTH, HEIGHT = 720, 1280


# ------------------------------------------------------------------------------
# FONT RESOLUTION (Windows + Linux safe)
# ------------------------------------------------------------------------------
def get_font_path(size, bold=True):
    # 1) Fonts BUNDLED in the repo (work on ANY OS: Windows, Streamlit Cloud, VPS)
    _fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    bundled = "Montserrat-Bold.ttf" if bold else "Montserrat-Regular.ttf"
    try:
        _p = os.path.join(_fonts_dir, bundled)
        if os.path.exists(_p):
            return _p
    except Exception:
        pass
    # 2) System fonts (fallbacks)
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\georiab.ttf" if bold else r"C:\Windows\Fonts\georgia.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        try:
            if os.path.exists(p):
                return p
        except Exception:
            continue
    return None


def get_pil_font(size, bold=True, text=None):
    # Devanagari/Hindi (and other non-Latin scripts) need a unicode font —
    # Montserrat renders them as tofu boxes. Auto-switch per text (script-aware).
    if text is not None and text_needs_unicode_font(text):
        return _get_unicode_font(size, bold, text=text)
    path = get_font_path(size, bold)
    try:
        if path:
            return ImageFont.truetype(path, size)
        return ImageFont.load_default(size=size)
    except TypeError:
        try:
            return ImageFont.load_default()
        except Exception:
            return ImageFont.load_default()


# anything outside basic Latin / Latin-ext / Greek / Cyrillic = needs a unicode font
_NON_LATIN_RE = re.compile(r"[^\x00-\x7F\u00A0-\u024F\u0370-\u03FF\u0400-\u04FF]")
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")


def text_needs_unicode_font(text):
    return bool(_NON_LATIN_RE.search(str(text or "")))


def _is_devanagari(text):
    return bool(_DEVANAGARI_RE.search(str(text or "")))


def _unicode_font_paths(text, bold=True):
    """Script-specific candidates.
    Devanagari (Hindi): Noto Sans Devanagari (bundled) -> Windows Mangal -> DejaVu.
    NOTE: DejaVu Sans has NO Devanagari glyphs — it would render tofu boxes.
    Other non-Latin: DejaVu (bundled) -> system DejaVu."""
    _d = os.path.dirname(os.path.abspath(__file__))
    if _is_devanagari(text):
        return [
            os.path.join(_d, "fonts", "NotoSansDevanagari-Bold.ttf" if bold else "NotoSansDevanagari-Regular.ttf"),
            r"C:\Windows\Fonts\mangal.ttf",   # Windows' built-in Devanagari font
            os.path.join(_d, "fonts", "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
        ]
    return [
        os.path.join(_d, "fonts", "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        r"C:\Windows\Fonts\mangal.ttf",
    ]


def _get_unicode_font(size, bold=True, text="द"):
    for p in _unicode_font_paths(text, bold):
        try:
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def get_font_path_for_text(text, size, bold=True):
    """Path-aware twin of get_pil_font (for callers that load the font themselves)."""
    if text_needs_unicode_font(text):
        for p in _unicode_font_paths(text, bold):
            if os.path.exists(p):
                return p
        return None
    return get_font_path(size, bold)


# ------------------------------------------------------------------------------
# CROSS-VERSION MOVIEPY HELPERS
# ------------------------------------------------------------------------------
def clip_fl(clip, fn):
    """Version-safe frame transform for video/image clips."""
    if hasattr(clip, "transform"):
        return clip.transform(fn)
    if hasattr(clip, "fl"):
        return clip.fl(fn)
    raise AttributeError("No transform/fl available on clip")


def set_opacity(clip, opacity):
    if hasattr(clip, "with_opacity"):
        return clip.with_opacity(opacity)
    if hasattr(clip, "set_opacity"):
        return clip.set_opacity(opacity)
    raise AttributeError("No opacity setter available")


def set_mask(clip, mask):
    if hasattr(clip, "with_mask"):
        return clip.with_mask(mask)
    if hasattr(clip, "set_mask"):
        return clip.set_mask(mask)
    raise AttributeError("No mask setter available")


# ------------------------------------------------------------------------------
# TEXT RENDERING (PIL — full control, Windows-safe, no emoji)
# ------------------------------------------------------------------------------
def _wrap_words(words, max_chars):
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def _measure_text(text, font, outline_width):
    tmp = Image.new("RGBA", (10, 10))
    d0 = ImageDraw.Draw(tmp)
    try:
        bbox = d0.textbbox((0, 0), text, font=font, stroke_width=outline_width)
        return bbox[2] - bbox[0], bbox[3] - bbox[1], bbox[0], bbox[1]
    except Exception:
        tw, th = d0.textsize(text, font=font)
        return tw, th, 0, 0


def fit_font_size(text, font_size, max_width=660, outline_width=7):
    """Shrink font so the whole line fits in max_width (single line, never wraps)."""
    font = get_pil_font(font_size, bold=True, text=text)
    tw, _, _, _ = _measure_text(text, font, outline_width)
    tw += outline_width * 2 + 8
    if tw > max_width and len(text) > 2:
        new_size = max(28, int(font_size * (max_width / tw) * 0.98))
        if new_size < font_size:
            return new_size
    return font_size


def render_text_image(text, font_size=80, color=(255, 255, 255),
                      outline_color=(0, 0, 0), outline_width=7,
                      panel=False, panel_color=(8, 10, 16, 210),
                      pad=28, max_width=660, cursor=False):
    """Render ONE line of text with heavy outline (auto-shrinks to fit, never wraps).
    cursor=True appends a typewriter bar after the text (GOONINGGNG captions)."""
    text = text.strip()
    font_size = fit_font_size(text, font_size, max_width, outline_width)
    font = get_pil_font(font_size, bold=True, text=text)
    tw, th, off_x, off_y = _measure_text(text, font, outline_width)
    tw += outline_width * 2 + 8
    th += outline_width * 2 + 8

    img = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if panel:
        d.rounded_rectangle([(6, 6), (img.width - 7, img.height - 7)],
                            radius=22, fill=panel_color, outline=(255, 255, 255, 90), width=2)
    d.text((pad - off_x, pad - off_y),
           text, font=font, fill=color + (255,), stroke_width=outline_width, stroke_fill=outline_color + (255,))
    if cursor:
        pass # User hates the cursor | symbol, disabled permanently.
    return img


def _pop_scale(t, t0, dur_in=0.16):
    """Spring pop: 0.82 -> 1.05 -> 1.0"""
    lt = t - t0
    if lt < 0:
        return 0.001
    if lt < 0.08:
        return 0.82 + (1.05 - 0.82) * (lt / 0.08)
    if lt < 0.08 + dur_in:
        k = (lt - 0.08) / dur_in
        return 1.05 - 0.05 * (1 - math.cos(k * math.pi)) / 2
    return 1.0


def make_text_pop_clip(img, start_t, pos, hold_dur, y_bob=0.0, bob_period=1.3):
    """Wrap a pre-rendered RGBA text image with spring pop-in scale animation."""
    from moviepy import ImageClip
    arr = np.array(img)
    clip = ImageClip(arr, transparent=True)
    try:
        clip = clip.resized(lambda t: max(_pop_scale(t, 0.0), 0.001))
    except Exception:
        pass
    clip = clip.with_duration(hold_dur).with_start(start_t)
    if y_bob:
        def pos_fn(t):
            x, y = pos
            return (x, y + y_bob * math.sin(2 * math.pi * t / bob_period))
        return clip.with_position(pos_fn)
    return clip.with_position(pos)


# ------------------------------------------------------------------------------
# ANIMATED STYLE BACKGROUNDS (numpy, fast, always-on, luminance floor)
# ------------------------------------------------------------------------------
def _radial_glow(w, h, cx, cy, radius, color, strength):
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / max(radius, 1)
    fall = np.clip(1.0 - d, 0, 1) ** 2
    out = np.zeros((h, w, 3), dtype=np.float32)
    for i in range(3):
        out[..., i] = fall * color[i] * strength
    return out


def _make_grid_base(accent, style):
    base = Image.new("RGB", (WIDTH, HEIGHT))
    px = base.load()
    if style == "pinstripe":
        bg = (46, 10, 16)
        stripe = (94, 22, 30)
        for x in range(WIDTH):
            c = stripe if (x % 10) < 2 else bg
            for y in range(0, HEIGHT, 4):
                for dy in range(4):
                    px[x, y + dy] = c
    else:
        bg = (9, 9, 13)
        for y in range(HEIGHT):
            for x in range(0, WIDTH, 4):
                for dx in range(4):
                    px[x + dx, y] = bg
    return base


def _make_grid_lines():
    """Dashed gray grid (transparent elsewhere) — the reference 'elite grid'."""
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cell = 90
    dash, gap = 26, 18
    for gx in range(0, WIDTH + 1, cell):
        y = 0
        while y < HEIGHT:
            d.line([(gx, y), (gx, min(y + dash, HEIGHT))], fill=(165, 165, 180, 62), width=2)
            y += dash + gap
    for gy in range(0, HEIGHT + 1, cell):
        x = 0
        while x < WIDTH:
            d.line([(x, gy), (min(x + dash, WIDTH), gy)], fill=(165, 165, 180, 62), width=2)
            x += dash + gap
    return np.array(img)


# ------------------------------------------------------------------------------
# TEXT-FIRST FALLBACK CLIP (pro Tool 3): when a word has no footage,
# the word ITSELF becomes the visual — huge accent word on the style background
# ------------------------------------------------------------------------------
def make_keyword_clip(keyword, duration, accent="yellow", style="grid"):
    from moviepy import VideoClip
    accent_rgb = ACCENTS.get(accent, ACCENTS["yellow"])
    text_img = render_text_image(str(keyword).upper(), font_size=92,
                                 color=accent_rgb, outline_width=8)
    if text_img.width > 600:
        text_img = text_img.resize((600, int(text_img.height * 600 / text_img.width)), Image.LANCZOS)
    tarr = np.array(text_img)
    tw, th = text_img.width, text_img.height
    tx, ty = (WIDTH - tw) // 2, (HEIGHT - th) // 2 - 60
    bg = make_style_background_clip(duration, style=style, accent=accent)

    def make_frame(t):
        frame = bg.get_frame(t).copy()
        s = 0.85 + 0.15 * min(1.0, t / 0.25)   # pop-in scale
        w2, h2 = max(1, int(tw * s)), max(1, int(th * s))
        timg = text_img.resize((w2, h2), Image.BILINEAR) if (w2, h2) != (tw, th) else text_img
        ta = np.array(timg)
        x0 = max(0, min(tx - (w2 - tw) // 2, WIDTH - w2))
        y0 = max(0, min(ty - (h2 - th) // 2, HEIGHT - h2))
        a = ta[..., 3:4].astype(float) / 255.0
        region = frame[y0:y0 + h2, x0:x0 + w2]
        frame[y0:y0 + h2, x0:x0 + w2] = (region * (1 - a) + ta[..., :3] * a).astype("uint8")
        return frame

    return VideoClip(make_frame, duration=duration)


def _make_starfield():
    """Static starfield for the cosmic (cinematic) background style."""
    rng = np.random.default_rng(7)
    stars = np.zeros((HEIGHT, WIDTH), dtype=np.float32)
    for _ in range(240):
        x = int(rng.integers(0, WIDTH)); y = int(rng.integers(0, HEIGHT))
        r = int(rng.integers(1, 3))
        v = rng.uniform(40, 160)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                yy, xx = y + dy, x + dx
                if 0 <= yy < HEIGHT and 0 <= xx < WIDTH and dx * dx + dy * dy <= r * r:
                    stars[yy, xx] = min(255.0, stars[yy, xx] + v)
    return stars


def _make_vignette():
    img = Image.new("L", (WIDTH, HEIGHT), 0)
    d = ImageDraw.Draw(img)
    cx, cy = WIDTH // 2, HEIGHT // 2
    max_r = int(math.hypot(cx, cy))
    for r in range(max_r, 0, -6):
        opacity = int((r / max_r) ** 2.0 * 150)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=opacity, width=6)
    return np.array(img).astype(np.float32) / 255.0


def make_style_background_clip(duration, style="grid", accent="yellow", fps=24):
    """Always-on dark style background. NEVER pure black: grid/stripes + glow + floor."""
    from moviepy import VideoClip
    accent_rgb = np.array(ACCENTS.get(accent, ACCENTS["yellow"]), dtype=np.float32)

    if style == "void":
        # GOONINGGNG base: near-black void + faint static starfield, no grid,
        # no glow. The B-roll (cosmic-graded) IS the visual.
        base_img = Image.new("RGB", (WIDTH, HEIGHT), (4, 4, 7))
        grid_arr = None
        glow = np.zeros((HEIGHT, WIDTH, 3), dtype=np.float32)
        glow2 = None
        stars_arr = (_make_starfield() * 0.45).astype(np.float32)
    elif style == "pinstripe":
        base_img = _make_grid_base(accent, "pinstripe")
        grid_arr = None
        glow = _radial_glow(WIDTH, HEIGHT, WIDTH // 2, int(HEIGHT * 0.95), 700, accent_rgb, 0.16)
        glow2 = _radial_glow(WIDTH, HEIGHT, int(WIDTH * 0.15), HEIGHT, 500, (255, 255, 255), 0.03)
    else:  # grid / aurora / glow
        base_img = _make_grid_base(accent, "grid")
        if style == "aurora":
            grid_arr = None
            glow = (_radial_glow(WIDTH, HEIGHT, int(WIDTH * 0.25), int(HEIGHT * 0.30), 480, (80, 70, 230), 0.14)
                    + _radial_glow(WIDTH, HEIGHT, int(WIDTH * 0.75), int(HEIGHT * 0.22), 460, (20, 180, 170), 0.12)
                    + _radial_glow(WIDTH, HEIGHT, int(WIDTH * 0.62), int(HEIGHT * 0.78), 520, (210, 60, 130), 0.10)
                    + _radial_glow(WIDTH, HEIGHT, int(WIDTH * 0.30), int(HEIGHT * 0.85), 480, (120, 90, 240), 0.12))
            glow2 = None
        elif style == "glow":
            grid_arr = None
            glow = (_radial_glow(WIDTH, HEIGHT, 0, HEIGHT, 620, accent_rgb, 0.16)
                    + _radial_glow(WIDTH, HEIGHT, WIDTH, 0, 560, accent_rgb, 0.08))
            glow2 = None
        elif style == "cosmic":
            # Cinematic mystery (reference #3): starfield + slow gold/blue nebula, no grid
            grid_arr = None
            glow = _radial_glow(WIDTH, HEIGHT, int(WIDTH * 0.5), int(HEIGHT * 0.42), 640, (212, 175, 55), 0.10)
            glow2 = _radial_glow(WIDTH, HEIGHT, int(WIDTH * 0.28), int(HEIGHT * 0.72), 500, (90, 110, 180), 0.07)
        else:  # grid (default elite)
            grid_arr = _make_grid_lines()
            glow = _radial_glow(WIDTH, HEIGHT, WIDTH // 2, int(HEIGHT * 0.98), 760, accent_rgb, 0.14)
            glow2 = _radial_glow(WIDTH, HEIGHT, WIDTH // 2, int(HEIGHT * 0.98), 420, (255, 255, 255), 0.035)

    stars_arr = _make_starfield() if style == "cosmic" else None
    base_arr = np.array(base_img).astype(np.float32)
    vig = _make_vignette()
    # pre-split grid arrays once (avoid per-frame dtype casts = fewer temp allocations)
    if grid_arr is not None:
        grid_rgb = grid_arr[..., :3].astype(np.float32)
        grid_a = (grid_arr[..., 3:4].astype(np.float32) / 255.0)

    def make_frame(t):
        frame = base_arr.copy()
        if grid_arr is not None:
            shift = int((t * 14) % 54)  # slow drift
            rolled_rgb = np.roll(grid_rgb, shift, axis=0)
            rolled_a = np.roll(grid_a, shift, axis=0)
            frame *= (1.0 - rolled_a)
            frame += rolled_rgb * rolled_a
        frame += glow * (1.0 + 0.10 * math.sin(t * 0.9))
        if glow2 is not None:
            frame += glow2 * (1.0 + 0.15 * math.sin(t * 0.6 + 1.2))
        if stars_arr is not None:
            # slow starfield drift (3px/s) + gentle twinkle via pulse
            sy = int((t * 3) % HEIGHT)
            frame += np.roll(stars_arr, sy, axis=0)[..., None] * (0.45 + 0.15 * math.sin(t * 0.5))
        frame *= (1.0 - vig[..., None] * 0.55)
        # luminance floor: frame must never die to black
        np.maximum(frame, 7.0, out=frame)
        np.clip(frame, 0, 255, out=frame)
        return frame.astype("uint8")

    return VideoClip(make_frame, duration=duration)


# ------------------------------------------------------------------------------
# GRAPHIC CARDS (pre-rendered images — the "information layer")
# ------------------------------------------------------------------------------
def _redact_scribble(d, x0, y0, x1, y1, seed=7):
    rng = random.Random(seed)
    for _ in range(5):
        yy = rng.randint(y0 + 4, y1 - 4)
        d.line([(x0, yy), (x1, yy + rng.randint(-5, 5))], fill=(225, 28, 40, 235), width=rng.randint(9, 14))
    for _ in range(3):
        yy = rng.randint(y0 + 4, y1 - 4)
        d.line([(x0 + 4, yy + 2), (x1 - 4, yy - 2)], fill=(180, 20, 30, 220), width=6)


def make_curiosity_card(title, items, redact=True, accent="yellow", w=600, h=520, visible_count=3):
    accent_rgb = ACCENTS.get(accent, ACCENTS["yellow"])
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([(12, 12), (w - 13, h - 13)], radius=34,
                        fill=(10, 12, 18, 255), outline=(255, 255, 255, 255), width=4)
    f_title = get_pil_font(44, bold=True)
    d.text((44, 44), title.upper(), font=f_title, fill=(255, 255, 255, 255),
           stroke_width=3, stroke_fill=(0, 0, 0, 255))
    # accent underline
    d.rectangle([(44, 108), (220, 114)], fill=accent_rgb + (255,))
    f_body = get_pil_font(34, bold=True)
    y = 160
    for i, item in enumerate(items[:3]):
        if i >= visible_count:
            break
        # strip any leading "N." the script already contains (avoids "3. 3." double numbering)
        clean_item = re.sub(r"^\s*\d+[\.\)]\s*", "", str(item))
        text = f"{i+1}.  {clean_item}"
        d.text((48, y), text, font=f_body, fill=(245, 245, 245, 255),
               stroke_width=2, stroke_fill=(0, 0, 0, 255))
        if redact and i == 0:
            d0 = d.textbbox((48, y), text, font=f_body)
            _redact_scribble(d, d0[0] + 60, d0[1] + 4, d0[2] - 6, d0[3] - 4, seed=11 + i)
        y += 112
    return img


def make_stat_card(big_text, sub_text, accent="yellow", w=430, h=300):
    accent_rgb = ACCENTS.get(accent, ACCENTS["yellow"])
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([(10, 10), (w - 11, h - 11)], radius=30,
                        fill=(248, 248, 248, 255), outline=(0, 0, 0, 255), width=3)
    f_big = get_pil_font(86, bold=True)
    f_sub = get_pil_font(28, bold=True)
    d.text((36, 40), big_text, font=f_big, fill=(15, 15, 20, 255),
           stroke_width=2, stroke_fill=(0, 0, 0, 100))
    d.text((40, 175), str(sub_text).upper()[:10], font=f_sub, fill=(60, 60, 70, 255))
    # green up-arrow badge
    cx, cy, r = w - 86, h - 84, 44
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 178, 90, 255))
    d.polygon([(cx, cy - 24), (cx + 20, cy + 8), (cx + 7, cy + 8), (cx + 7, cy + 24),
               (cx - 7, cy + 24), (cx - 7, cy + 8), (cx - 20, cy + 8)], fill=(255, 255, 255, 255))
    return img


def make_before_after_card(before_val, after_val, accent="yellow", w=640, h=400):
    """Algrow-style polarity card: red BEFORE panel vs green AFTER panel.
    Long values auto-shrink to fit their panel."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # left (red/negative)
    d.rounded_rectangle([(10, 10), (w // 2 - 8, h - 11)], radius=26, fill=(122, 18, 26, 255))
    # right (green/positive)
    d.rounded_rectangle([(w // 2 + 8, 10), (w - 11, h - 11)], radius=26, fill=(0, 128, 62, 255))
    f_lab = get_pil_font(38, bold=True)
    d.text((40, 40), "BEFORE", font=f_lab, fill=(255, 255, 255, 255))
    d.text((w // 2 + 38, 40), "AFTER", font=f_lab, fill=(255, 255, 255, 255))
    # value chips
    chip_h = 120
    d.rounded_rectangle([(34, 130), (w // 2 - 34, 130 + chip_h)], radius=18, fill=(250, 250, 250, 255))
    d.rounded_rectangle([(w // 2 + 34, 130), (w - 34, 130 + chip_h)], radius=18, fill=(250, 250, 250, 255))

    def _draw_value(text, x0, x1, color):
        text = str(text)[:24]
        max_w = (x1 - x0) - 40
        size = 48
        while size > 16:
            f = get_pil_font(size, bold=True)
            tw, th, ox, oy = _measure_text(text, f, 0)
            if tw <= max_w:
                break
            size -= 2
        f = get_pil_font(size, bold=True)
        tw, th, ox, oy = _measure_text(text, f, 0)
        cx = (x0 + x1) // 2
        d.text((cx - tw // 2 - ox, 130 + (chip_h - th) // 2 - oy), text, font=f, fill=color + (255,))

    _draw_value(before_val, 34, w // 2 - 34, (150, 20, 26))
    _draw_value(after_val, w // 2 + 34, w - 34, (0, 110, 50))
    # step labels
    d.text((40, 280), "STATE 0", font=f_lab, fill=(255, 200, 200, 235))
    d.text((w // 2 + 38, 280), "STATE 1", font=f_lab, fill=(210, 255, 230, 235))
    return img


def make_arrow_img(color=(255, 196, 0), w=300, h=260):
    """Curved hand-drawn style arrow (accent color with white rim)."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # quadratic bezier from top-left to bottom-right
    p0, p1, p2 = (30, 20), (10, 190), (240, 220)
    pts = []
    for i in range(41):
        t = i / 40
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        pts.append((x, y))
    for i in range(len(pts) - 1):
        lw = max(8, int(30 * (1 - i / len(pts)) * 0.5 + 8))
        d.line([pts[i], pts[i + 1]], fill=(255, 255, 255, 255), width=lw + 6)
    for i in range(len(pts) - 1):
        lw = max(6, int(26 * (1 - i / len(pts)) * 0.5 + 6))
        d.line([pts[i], pts[i + 1]], fill=color + (255,), width=lw)
    # arrowhead
    ex, ey = pts[-1]
    d.polygon([(ex + 46, ey + 18), (ex - 18, ey - 26), (ex + 6, ey + 46)], fill=color + (255,))
    d.polygon([(ex + 52, ey + 18), (ex - 26, ey - 30), (ex + 4, ey + 54)], outline=(255, 255, 255, 255), width=4)
    return img


# ------------------------------------------------------------------------------
# SFX SYNTHESIS (WAV, mono, 44.1k)
# ------------------------------------------------------------------------------
def _write_wav(path, samples, sample_rate=44100):
    import wave
    data = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(data.tobytes())


def generate_sfx_hit(sfx_dir, name="sfx_hit.wav", duration=0.55):
    path = os.path.join(sfx_dir, name)
    if os.path.exists(path):
        return path
    sr = 44100
    n = int(sr * duration)
    t = np.arange(n) / sr
    f0, f1 = 62.0, 27.0
    phase = 2 * np.pi * (f0 * (1 - np.exp(-7 * t)) / 7 + f1 * t)
    env = np.exp(-7.5 * t)
    wave_sig = np.sin(phase) * env
    # attack click
    click = np.random.uniform(-1, 1, n) * np.exp(-t * 160) * 0.5
    _write_wav(path, (wave_sig * 0.95 + click * 0.4))
    return path


def generate_sfx_riser(sfx_dir, name="sfx_riser.wav", duration=1.2):
    path = os.path.join(sfx_dir, name)
    if os.path.exists(path):
        return path
    sr = 44100
    n = int(sr * duration)
    t = np.arange(n) / sr
    k = t / duration
    env = k ** 2.2
    noise = np.random.uniform(-1, 1, n)
    # crude lowpass
    kernel = np.ones(9) / 9
    noise_lp = np.convolve(noise, kernel, mode="same")
    f = 140 + 2600 * k ** 1.7
    phase = 2 * np.pi * np.cumsum(f) / sr
    sine = np.sin(phase) * 0.25
    _write_wav(path, (noise_lp * 0.55 + sine) * env)
    return path


def generate_sfx_impact(sfx_dir, name="sfx_impact.wav", duration=0.8):
    path = os.path.join(sfx_dir, name)
    if os.path.exists(path):
        return path
    sr = 44100
    n = int(sr * duration)
    t = np.arange(n) / sr
    boom = np.sin(2 * np.pi * (46 * np.exp(-3 * t) + 30) * t) * np.exp(-5.5 * t)
    noise = np.random.uniform(-1, 1, n)
    kernel = np.ones(25) / 25
    noise_lp = np.convolve(noise, kernel, mode="same") * np.exp(-11 * t) * 0.5
    _write_wav(path, boom * 0.95 + noise_lp)
    return path


def generate_sfx_ding(sfx_dir, name="sfx_ding.wav", duration=0.4):
    path = os.path.join(sfx_dir, name)
    if os.path.exists(path):
        return path
    sr = 44100
    n = int(sr * duration)
    t = np.arange(n) / sr
    wave_sig = (np.sin(2 * np.pi * 1318 * t) * 0.5 + np.sin(2 * np.pi * 1975 * t) * 0.3) * np.exp(-9 * t)
    _write_wav(path, wave_sig * 0.8)
    return path


# ------------------------------------------------------------------------------
# SCRIPT -> BEATS PARSER
# ------------------------------------------------------------------------------
def parse_hook_lines(script_text, max_lines=3, max_words=3):
    lines = [l.strip() for l in script_text.split("\n") if l.strip()]
    content = [re.sub(r"\[.*?\]", "", l).strip() for l in lines
               if not (l.strip().startswith("[") and l.strip().endswith("]"))]
    content = [c for c in content if c]
    if not content:
        return ["WATCH", "THIS"]
    hook = content[0]
    # take first sentence only (the actual hook, not the whole paragraph)
    first_sent = re.split(r"(?<=[\.\!\?])\s+", hook)[0]
    words = re.sub(r"[^\w\s%']", "", first_sent).split()[:12]
    out, cur = [], ""
    for w in words:
        if cur and len(cur.split()) >= max_words:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        # merge a lone trailing word into the previous line
        if len(cur.split()) < 2 and out:
            out[-1] = f"{out[-1]} {cur}".strip()
        else:
            out.append(cur)
    return out[:max_lines]


BEAT_STOP_WORDS = {"to", "the", "is", "a", "an", "of", "your", "so", "and",
                   "that", "this", "in", "on", "for", "with", "you", "or", "it"}


def _clean_beat_words(words, max_words=4):
    """Skip leading stop-words, cut at the first inner stop-word."""
    i = 0
    while i < len(words) and words[i].lower().strip(".,!?") in BEAT_STOP_WORDS:
        i += 1
    out = []
    for w in words[i:]:
        if w.lower().strip(".,!?") in BEAT_STOP_WORDS:
            break
        out.append(w)
        if len(out) >= max_words:
            break
    return out


def parse_beats(script_text):
    """Return (beats, card_items, has_stat, stat_text)"""
    beats = []
    for l in script_text.split("\n"):
        ls = l.strip()
        m = re.match(r"^(\d+)[\.\)]\s*(.+)$", ls)
        if m:
            body = re.sub(r"\[.*?\]", "", m.group(2))
            body = re.sub(r"[^\w\s%\-']", "", body)
            bw = _clean_beat_words(body.split()[:8])
            if bw:
                beat_text = m.group(1) + ". " + " ".join(bw)
                beats.append(beat_text.upper())
    card_items = []
    sm = re.search(r"\[SAVE_TRIGGER_LIST:\s*(.*?)\]", script_text)
    if sm:
        card_items = [p.strip() for p in sm.group(1).split("|") if p.strip()][:3]
    has_stat = False
    stat_text = ""
    mnum = re.search(r"(\d{1,3})\s*%", script_text)
    if mnum:
        has_stat = True
        stat_text = f"{mnum.group(1)}%"
    return beats, card_items, has_stat, stat_text


def _find_word_time(word, vtt_subs, after_t):
    w = word.lower()
    if not w or not w.isalpha():
        return None
    for s in vtt_subs:
        if s["start"] < after_t:
            continue
        if w in s["text"].lower():
            return s["start"]
    return None


def schedule_beats(beats, vtt_subs, duration):
    """Assign each beat a start time: sync to the spoken word when possible."""
    timed = []
    after_t = 2.6
    window_end = max(4.0, duration - 6.0)
    for i, b in enumerate(beats):
        # first real content word (skip the "1." prefix and leading stop-words)
        alpha_words = [w.strip(".!?,") for w in b.split() if w.strip(".!?,").isalpha()]
        cleaned = _clean_beat_words(alpha_words, max_words=4)
        first_word = cleaned[0].lower() if cleaned else (alpha_words[0].lower() if alpha_words else "")
        t = _find_word_time(first_word, vtt_subs, after_t)
        if t is None or t > window_end + 1.5:
            t = after_t + (window_end - after_t) * (i / max(1, len(beats)))
        t = max(after_t, min(t, window_end))
        timed.append((t, b))
        after_t = t + 1.2
    return timed


# ------------------------------------------------------------------------------
# ELITE TEXT LAYER — the full composition (hook + beats + cards + arrow + sfx)
# ------------------------------------------------------------------------------
def build_elite_text_layer(script_text, vtt_subs, duration, accent="yellow",
                           sfx_dir="audio_clips", show_card=True,
                           hook_style="uniform", hook_hold=3.2):
    """
    Returns (video_clips, sfx_events)
    sfx_events: list of (wav_path, start_t, volume)
    hook_style: 'uniform' (all lines same size, accent on last)
                'stack_contrast' (GOONINGGNG: small accent line + HUGE white line)
    """
    from moviepy import ImageClip
    accent_rgb = ACCENTS.get(accent, ACCENTS["yellow"])
    clips = []
    sfx_events = []

    # ---- 1. STACKED HOOK DISABLED ----
    # User feedback: The static stacked hook clashes with the dynamic 1-word captions 
    # and clutters the screen. We now rely exclusively on the high-retention dynamic captions.
    pass
    # v2: soft hook hit (the old 0.5 volume startle was a skip trigger)
    sfx_events.append(("__hit__", 0.42, 0.32))

    # ---- 2. BEAT TEXT (synced to spoken words), upper-mid ----
    beats, card_items, has_stat, stat_text = parse_beats(script_text)
    timed_beats = schedule_beats(beats[:4], vtt_subs, duration)
    for t0, text in timed_beats:
        try:
            img = render_text_image(text, font_size=54, color=(255, 255, 255),
                                    outline_width=5, panel=True)
            if img.width > 640:
                img = img.resize((640, int(img.height * 640 / img.width)), Image.LANCZOS)
            c = make_text_pop_clip(img, t0, ("center", 560), 2.0, y_bob=5)
            clips.append(c)
            # v2: NO pop per beat (random tick = distraction). Power-word ticks
            # in the caption layer handle the audio accent, synced to the voice.
        except Exception as e:
            print(f"[StyleEngine] beat failed: {e}")

    # ---- 3. CURIOSITY CARD (redacted) + REVEAL ----
    if show_card and card_items:
        # LIST CARD COMPLETELY DISABLED PER USER REQUEST
        pass

    # ---- 4. STAT PROOF CARD (if script has a % number) — shown DURING the hook,
    # small, mid-left, never colliding with the list card or captions ----
    if has_stat:
        try:
            stat = make_stat_card(stat_text, "of people fail", accent=accent, w=330, h=235)
            c = make_text_pop_clip(Image.fromarray(np.array(stat)), 1.0, (36, 470), 2.1)
            clips.append(c)
            # v2: silent entrance (SFX budget)
        except Exception as e:
            print(f"[StyleEngine] stat card failed: {e}")

    # ---- 5. BEFORE/AFTER POLARITY CARD (Algrow signature) — problem → solution ----
    if len(timed_beats) >= 2 and duration >= 20:
        try:
            def _short(beat_text, maxw=2):
                out = []
                for w in str(beat_text).split():
                    if re.match(r"^\d+[\.\)]$", w):
                        continue
                    out.append(w.strip(".,!"))
                    if len(out) >= maxw:
                        break
                return " ".join(out).title() or "Fixed"
            before_txt = _short(timed_beats[0][1])
            after_txt = _short(timed_beats[-1][1])
            ba = make_before_after_card(before_txt, after_txt, accent=accent, w=620, h=390)
            _rv = locals().get("reveal_t") or 0.0
            ba_start = max(min(timed_beats[-1][0] + 2.4, duration - 5.5), _rv + 2.8 if _rv else 0.0)
            ba_hold = max(2.0, min(duration - 1.0, ba_start + 4.2) - ba_start)
            c = make_text_pop_clip(Image.fromarray(np.array(ba)), ba_start, ("center", 420), ba_hold)
            clips.append(c)
            # v2: silent entrance (SFX budget — the video is already at its energy peak)
        except Exception as e:
            print(f"[StyleEngine] before/after card failed: {e}")

    # ---- 6. v2: LOOP HIT — soft hit on the final "and that is because..." moment ----
    # (removed: mid-video riser + impact; the only big moment is the reveal)
    if duration > 8:
        sfx_events.append(("__hit__", duration - 0.45, 0.30))

    return clips, sfx_events


# ------------------------------------------------------------------------------
# FRAME GRADING — Shorts-compression-compensated premium dark grade
# ------------------------------------------------------------------------------
def grade_frame(arr):
    """
    Mid-gray darkening (the 'dark premium' look) + contrast +10% + saturation +15%
    + tiny brightness lift so footage never dies to black.
    """
    a = arr.astype(np.float32)
    # contrast 1.10 around mid
    a = (a - 128.0) * 1.10 + 128.0
    # mid-gray darkening: pull luma<110 pixels down
    luma = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    dark_mask = np.clip((110.0 - luma) / 110.0, 0, 1)[..., None]
    a = a * (1.0 - dark_mask * 0.22)
    # saturation +15%
    sat = a.max(axis=2, keepdims=True)
    a = a + (sat - a) * 0.15
    # brightness floor
    a = a + 4.0
    return np.clip(a, 0, 255).astype("uint8")


def grade_clip_dark(arr_factor=0.62):
    """Darker grade for B-roll that sits UNDER the style system (blend mode)."""
    def fn(frame):
        a = grade_frame(frame).astype(np.float32) * arr_factor
        return np.clip(a, 6, 255).astype("uint8")
    return fn


def daily_code(date_str=None):
    """B4 — THE DAILY CODE (the power ritual). Deterministic from the date:
    the same code all day, new code tomorrow. 'CODE 4-2-1' style."""
    d = date_str or datetime.date.today().strftime("%Y%m%d")
    h = zlib.crc32(f"faceless-code-{d}".encode())
    return f"{h % 10}-{(h // 10) % 10}-{(h // 100) % 10}"


def make_outro_card(handle, code, accent="yellow", w=720, h=1280):
    """GOONINGGNG outro (the last ~4s): near-black card, @handle centered,
    'the next code is dropping' line, and CODE X-Y-Z bottom-left (B4 ritual)."""
    img = Image.new("RGB", (w, h), (6, 6, 9))
    d = ImageDraw.Draw(img)
    rng = random.Random(99)
    for _ in range(70):
        x, y = rng.randint(0, w), rng.randint(0, h)
        v = rng.randint(22, 64)
        d.point((x, y), fill=(v, v, min(255, v + 8)))
    accent_rgb = ACCENTS.get(accent, ACCENTS["yellow"])
    handle_txt = str(handle or "").strip()
    if not handle_txt.startswith("@"):
        handle_txt = "@" + handle_txt
    f = get_pil_font(58, bold=True, text=handle_txt)
    tw, th, ox, oy = _measure_text(handle_txt, f, 3)
    if tw > w - 80:   # long handle: shrink to fit the card
        size = max(30, int(58 * (w - 80) / tw))
        f = get_pil_font(size, bold=True, text=handle_txt)
        tw, th, ox, oy = _measure_text(handle_txt, f, 3)
    d.text(((w - tw) // 2 - ox, h // 2 - 110 - oy), handle_txt, font=f,
           fill=(235, 238, 245), stroke_width=3, stroke_fill=(0, 0, 0))
    f2 = get_pil_font(28, bold=False, text="x")
    sub = "THE NEXT CODE IS DROPPING"
    tw2, th2, ox2, oy2 = _measure_text(sub, f2, 0)
    d.text(((w - tw2) // 2 - ox2, h // 2 + 30 - oy2), sub, font=f2, fill=(118, 124, 136))
    f3 = get_pil_font(34, bold=True, text=str(code))
    d.text((48, h - 150), f"CODE {code}", font=f3, fill=tuple(accent_rgb),
           stroke_width=2, stroke_fill=(0, 0, 0))
    return img


def make_sigil_overlay(duration, seed=1):
    """B5 — the insider mark: a small 12-point star shown for 2s at ~62% of the
    video, position seeded per video. Never announced ('only the real ones
    notice'). Pairs with A3 (the 1-frame code flash)."""
    from moviepy import ImageClip
    rng = random.Random(seed)
    size = 46
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = size // 2
    pts = []
    for i in range(24):
        r = 22 if i % 2 == 0 else 10
        a = math.pi * i / 12 - math.pi / 2
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=(255, 215, 0, 140))
    clip = ImageClip(np.array(img), transparent=True)
    t0 = max(0.5, duration * 0.62)
    pos = (rng.randint(60, WIDTH - 100), rng.randint(90, 320))
    return clip.with_start(t0).with_duration(2.0).with_position(pos)


def make_watermark_clip(handle, duration):
    """Watermark lock: @handle top-right, every frame, small + soft. The
    channel's brand signature (GOONINGGNG runs its IG handle on every frame)."""
    from moviepy import ImageClip
    txt = str(handle or "").strip()
    if not txt:
        return None
    if not txt.startswith("@"):
        txt = "@" + txt
    img = render_text_image(txt, font_size=30, color=(235, 238, 245), outline_width=2, pad=6)
    a = np.array(img).astype(np.float32)
    a[..., 3] *= 0.7
    clip = ImageClip(a.astype(np.uint8), transparent=True)
    return clip.with_duration(duration).with_position((WIDTH - img.width - 34, 46))


def grade_frame_cosmic(arr):
    """THE GOONINGGNG FILTER — measured from ref_video3 (31 frames):
       mean luminance 22/255, saturation 2.0%, 66% of pixels near-black.
       Full-color footage comes through as dark graphite + one faint hue.
       1) crush saturation to 12%  2) exposure-normalize to ~24 mean
       3) soft-clip highlights at ~160 (the ref's white nebula cores)
       4) luminance floor 3 (never true black — the no-dead-frame rule)"""
    a = arr.astype(np.float32)
    luma = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    a = 0.12 * a + 0.88 * luma[..., None]
    cur = float(a.mean())
    if cur > 1.0:
        a = a * (24.0 / cur)
    a = np.where(a > 160.0, 160.0 + (a - 160.0) * 0.25, a)
    a = np.clip(a, 8.0, 255)   # floor 8: near-black sources must keep visible structure
    return a.astype("uint8")
