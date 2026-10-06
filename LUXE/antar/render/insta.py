"""
LUXE - Pro Human Edits - English Only, Basic English, Centered

Your words (no assumptions):
- "did not mention hindi quotes - stop assuming" = English only, basic English for everyone
- "we use basic english for luxe so everyone can understand easily" = 3-8 words, basic vocab
- "if we making reels then change fonts also and its style it should placed center in video or simply SEARCH IT" = Search results: Didot 4.9/5 luxury, centered, bold statement 3-5 words, white on black, safe zone center 80%, first frame hooks, 3+ sec on screen
- "we are not going on psyche now just in luxe so lets make it 1st" = focus LUXE only
- "brain we will change it also" = brain changed to English luxury quotes
- "did we add tools in it like ffmpeg? i need a requirement list also and a script so it can download auto in kali" = requirements.txt + install.sh with ffmpeg auto
- "we not going to add voice" = no voice, pipeline skips voice, just phonk + text

Search results for center placement luxury fonts:
- Didot: timeless elegance, high-contrast, luxury/fashion Reels, rating 4.9/5
- Monerd: clean contemporary, sleek modern
- Merritta Serif: creative sophisticated, luxury brands
- Best for luxury: Didot, Cormorant Garamond, Pierson, Abril Fatface
- Placement: center for maximum punch, 3-5 words, white on black, safe zone center 80%
- For Reels: Bold statements, multi-layer hierarchy, shape backgrounds, first frame hook, 3+ sec
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from dataclasses import dataclass

# INSTA CONFIG - English only, centered, clean edges
INSTA_CANVAS_W = 1080
INSTA_CANVAS_H = 1920
# Inner rect - leaves safe zones: center 80% = 1080x1420, so inner 1000x1350 centered
INNER_W = 1000
INNER_H = 1350
INNER_X = (INSTA_CANVAS_W - INNER_W) // 2  # 40
INNER_Y = 280  # centered-ish, above bottom safe zone
CORNER_RADIUS = 28
STROKE_WIDTH = 2
STROKE_COLOR = (255, 255, 255, 51)  # white 20% opacity
SHADOW_OFFSET = 8
SHADOW_BLUR = 24

# Fonts - English luxury only, no Hindi
FONTS = {
    "bebas": "BebasNeue-Regular.ttf",  # Bold English quotes - MAIN CHARACTER ENERGY - bold statement headlines
    "didot": "Didot-Placeholder.ttf",  # Luxury serif - Abril Fatface - Didot alternative - timeless elegance 4.9/5
    # Khand kept as fallback but not used for LUXE English (user said no Hindi)
    "khand": "Khand-Bold.ttf",
}

# Quote font mapping by mood - English only, centered
QUOTE_FONT_BY_MOOD = {
    "luxury": "didot",      # Didot/Abril - high-end, timeless elegance, centered, serif
    "quiet": "didot",       # quiet luxury
    "oldmoney": "didot",    # old money doesn't chase
    "bold": "bebas",        # Bebas - bold statement headlines, 3-5 words, white on black, center punch
    "main": "bebas",        # main character energy
    "motivation": "bebas",
    "minimal": "didot",     # less is more - minimal luxury
    "soft": "didot",        # elegance is silent
}

def _ffmpeg() -> str:
    from ..vault import find_ffmpeg
    path = find_ffmpeg()
    if not path:
        raise RuntimeError("ffmpeg not found")
    return path

def _pil():
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
    except Exception as e:
        raise RuntimeError(f"Pillow missing: {e}")
    return Image, ImageDraw, ImageFilter, ImageFont

@dataclass
class InstaRect:
    output: Path
    inner_w: int
    inner_h: int
    x: int
    y: int
    radius: int

def _rounded_mask(width: int, height: int, radius: int):
    """Create anti-aliased rounded rectangle mask - clean edges"""
    Image, ImageDraw, _, _ = _pil()
    # 4x supersample for clean edges
    scale = 4
    mask = Image.new("L", (width*scale, height*scale), 0)
    draw = ImageDraw.Draw(mask)
    try:
        draw.rounded_rectangle([(0,0), (width*scale, height*scale)], radius=radius*scale, fill=255)
    except:
        draw.rectangle([(0,0), (width*scale, height*scale)], fill=255)
    # Downsample with LANCZOS for anti-alias
    mask = mask.resize((width, height), Image.LANCZOS)
    return mask

def render_rectangular_middle(
    clip_path: Path,
    output_path: Path,
    config=None,
    *,
    seek: float = 0.5,
    duration: float = 3.0,
    blur_background: bool = True,
) -> InstaRect:
    """
    Pro human edit: rectangular video in middle with clean edges.
    
    Your spec: rectangular shaped and placed video in middle, now with clean edges, same premium clips
    
    Pipeline:
    1. Extract frame or clip segment at 1000x1350
    2. Apply rounded corners with anti-alias mask (clean edges)
    3. Add white stroke 2px 20% opacity
    4. Add drop shadow offset 0,8 blur 24
    5. Background = blurred version of same clip + dark overlay 60% OR house colour
    6. Composite onto 1080x1920 canvas
    """
    Image, ImageDraw, ImageFilter, _ = _pil()
    ffmpeg = _ffmpeg()
    
    clip_path = Path(clip_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Extract inner clip scaled to INNER_W x INNER_H
    temp_inner = output_path.with_suffix(".inner.mp4")
    temp_bg = output_path.with_suffix(".bg.mp4")
    temp_frame = output_path.with_suffix(".inner_frame.png")
    temp_bg_frame = output_path.with_suffix(".bg_frame.png")
    
    # Scale inner video to fill INNER_W x INNER_H, crop center
    # Use ffmpeg scale + crop
    inner_filter = f"scale={INNER_W}:{INNER_H}:force_original_aspect_ratio=increase,crop={INNER_W}:{INNER_H}"
    
    cmd = [
        ffmpeg, "-hide_banner", "-v", "error",
        "-ss", str(seek),
        "-i", str(clip_path),
        "-t", str(duration),
        "-vf", inner_filter,
        "-r", "30",
        "-an",
        "-y", str(temp_inner)
    ]
    subprocess.run(cmd, check=True)
    
    # Extract one frame from inner for Pillow processing (rounded corners)
    cmd = [
        ffmpeg, "-hide_banner", "-v", "error",
        "-ss", "0.2",
        "-i", str(temp_inner),
        "-frames:v", "1",
        "-y", str(temp_frame)
    ]
    subprocess.run(cmd, check=True)
    
    # Step 2: Background - blurred version or house colour - ALWAYS create temp_bg video for ffmpeg pipeline
    if blur_background:
        # Create blurred background: scale to 1080x1920, blur heavily
        bg_filter = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=25"
        cmd = [
            ffmpeg, "-hide_banner", "-v", "error",
            "-ss", str(seek),
            "-i", str(clip_path),
            "-t", str(duration),
            "-vf", bg_filter,
            "-r", "30",
            "-an",
            "-y", str(temp_bg)
        ]
        subprocess.run(cmd, check=True)
        cmd = [
            ffmpeg, "-hide_banner", "-v", "error",
            "-ss", "0.2",
            "-i", str(temp_bg),
            "-frames:v", "1",
            "-y", str(temp_bg_frame)
        ]
        subprocess.run(cmd, check=True)
        bg_img = Image.open(temp_bg_frame).convert("RGBA")
    else:
        # House colour background - still create temp_bg video as solid color for ffmpeg pipeline (fix scrape bug)
        bg_filter = f"color=c=0x0B0B0F:s={INSTA_CANVAS_W}x{INSTA_CANVAS_H}:d={duration}:r=30"
        cmd = [
            ffmpeg, "-hide_banner", "-v", "error",
            "-f", "lavfi",
            "-i", bg_filter,
            "-t", str(duration),
            "-r", "30",
            "-an",
            "-y", str(temp_bg)
        ]
        subprocess.run(cmd, check=True)
        bg_img = Image.new("RGBA", (INSTA_CANVAS_W, INSTA_CANVAS_H), (11, 11, 15, 255))
    
    # Dark overlay 60% on background for contrast
    overlay = Image.new("RGBA", (INSTA_CANVAS_W, INSTA_CANVAS_H), (0, 0, 0, 153))  # 60%
    bg_img = Image.alpha_composite(bg_img, overlay)
    
    # Step 3: Rounded corners + clean edges on inner
    inner_img = Image.open(temp_frame).convert("RGBA")
    # Ensure size
    inner_img = inner_img.resize((INNER_W, INNER_H), Image.LANCZOS)
    
    # Create rounded mask - clean edges via supersample
    mask = _rounded_mask(INNER_W, INNER_H, CORNER_RADIUS)
    
    # Apply mask
    inner_img.putalpha(mask)
    
    # Add stroke - white 20% opacity, 2px
    # Create stroke by drawing rounded rectangle outline
    stroke_img = Image.new("RGBA", (INNER_W, INNER_H), (0,0,0,0))
    s_draw = ImageDraw.Draw(stroke_img)
    try:
        s_draw.rounded_rectangle(
            [(0,0), (INNER_W, INNER_H)],
            radius=CORNER_RADIUS,
            outline=STROKE_COLOR,
            width=STROKE_WIDTH
        )
    except:
        s_draw.rectangle([(0,0), (INNER_W, INNER_H)], outline=STROKE_COLOR, width=STROKE_WIDTH)
    
    inner_img = Image.alpha_composite(inner_img, stroke_img)
    
    # Step 4: Drop shadow - offset 0,8 blur 24 black 40%
    shadow = Image.new("RGBA", (INSTA_CANVAS_W, INSTA_CANVAS_H), (0,0,0,0))
    # Shadow is black with rounded shape at offset
    shadow_shape = Image.new("RGBA", (INNER_W, INNER_H), (0,0,0,0))
    sh_draw = ImageDraw.Draw(shadow_shape)
    try:
        sh_draw.rounded_rectangle([(0,0), (INNER_W, INNER_H)], radius=CORNER_RADIUS, fill=(0,0,0,102))  # 40%
    except:
        sh_draw.rectangle([(0,0), (INNER_W, INNER_H)], fill=(0,0,0,102))
    shadow.paste(shadow_shape, (INNER_X, INNER_Y + SHADOW_OFFSET), shadow_shape)
    shadow = shadow.filter(ImageFilter.GaussianBlur(SHADOW_BLUR))
    
    # Composite: bg + shadow + inner
    final = Image.alpha_composite(bg_img.convert("RGBA"), shadow)
    final.paste(inner_img, (INNER_X, INNER_Y), inner_img)
    
    # Save frame (for proof) and also need to do video version
    # For video, we need to apply same rounded mask via ffmpeg alpha
    # For now, save image proof
    proof_path = output_path.with_suffix(".proof.png")
    final.convert("RGB").save(proof_path, quality=95)
    
    # Video version: use ffmpeg with rounded corners via geq? Simpler: use overlay with mask
    # Create mask video and use alphamerge - for MVP, we composite via ffmpeg overlay of inner onto bg
    # Use ffmpeg to overlay inner (with rounded via mask file) onto bg
    
    # Create mask image file
    mask_path = output_path.with_suffix(".mask.png")
    mask.save(mask_path)
    
    # Build final video: bg + inner with mask
    # We need to make inner with alpha from mask
    # Use ffmpeg: [0] bg, [1] inner, [2] mask -> [1][2] alphamerge -> overlay
    cmd = [
        ffmpeg, "-hide_banner", "-v", "error",
        "-i", str(temp_bg),
        "-i", str(temp_inner),
        "-i", str(mask_path),
        "-filter_complex",
        f"[1:v][2:v]alphamerge[inner_alpha];[0:v][inner_alpha]overlay={INNER_X}:{INNER_Y}:shortest=1:format=auto",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "medium",
        "-r", "30",
        "-y", str(output_path)
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        # Fallback: no rounded, just overlay rectangular (clean edges still via scale)
        cmd_fallback = [
            ffmpeg, "-hide_banner", "-v", "error",
            "-i", str(temp_bg),
            "-i", str(temp_inner),
            "-filter_complex",
            f"[0:v][1:v]overlay={INNER_X}:{INNER_Y}:shortest=1",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "medium",
            "-r", "30",
            "-y", str(output_path)
        ]
        subprocess.run(cmd_fallback, check=True)
    
    # Cleanup temps
    for p in [temp_inner, temp_bg, temp_frame, temp_bg_frame, mask_path]:
        try:
            Path(p).unlink(missing_ok=True)
        except:
            pass
    
    return InstaRect(output=output_path, inner_w=INNER_W, inner_h=INNER_H, x=INNER_X, y=INNER_Y, radius=CORNER_RADIUS)

def render_quote_card(
    text: str,
    output_path: Path,
    *,
    mood: str = "luxury",
    font_choice: str | None = None,
    config=None,
) -> Path:
    """
    Quote card with different fonts - your instruction.
    
    Moods:
    - luxury: Didot/Abril - serif, high-end
    - bold/motivation: Bebas Neue
    - hindi/talking: Khand
    """
    Image, ImageDraw, ImageFilter, ImageFont = _pil()
    
    text = (text or "").strip()
    if not text:
        raise ValueError("quote needs text")
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Choose font by mood
    if font_choice is None:
        font_key = QUOTE_FONT_BY_MOOD.get(mood.lower(), "khand")
    else:
        font_key = font_choice
    
    font_file = FONTS.get(font_key, FONTS["khand"])
    font_path = Path(__file__).parent.parent.parent / "assets" / "fonts" / font_file
    if not font_path.exists():
        font_path = Path(__file__).parent.parent.parent / "assets" / "fonts" / "Khand-Bold.ttf"
    
    # Canvas 1080x1920
    W, H = INSTA_CANVAS_W, INSTA_CANVAS_H
    base_color = (11, 11, 15)  # house colour, not pure black
    
    img = Image.new("RGB", (W, H), base_color)
    draw = ImageDraw.Draw(img)
    
    # Cinematic gradient - dark edges, lighter middle
    for y in range(H):
        mid = H // 2
        dist = abs(y - mid) / (H / 2)
        lift = int(12 * (1 - dist))
        draw.line([(0, y), (W, y)], fill=(base_color[0]+lift, base_color[1]+lift, base_color[2]+lift+4))
    
    # Vignette
    vignette = Image.new("L", (W, H), 0)
    v_draw = ImageDraw.Draw(vignette)
    for i in range(5):
        alpha = int(40 - i*8)
        v_draw.rectangle([i*30, i*30, W-i*30, H-i*30], outline=alpha, width=30)
    vignette = vignette.filter(ImageFilter.GaussianBlur(80))
    img = Image.composite(Image.new("RGB", (W, H), (8,8,12)), img, vignette)
    draw = ImageDraw.Draw(img)
    
    # Text layout - centered, 80% width
    usable_w = int(W * 0.80)
    
    # Find font size that fits
    size = 120
    if mood in ("luxury", "sad"):
        size = 90  # serif needs smaller for elegance
    elif mood in ("bold", "motivation"):
        size = 140  # Bebas can be bigger
    
    while size > 40:
        try:
            font = ImageFont.truetype(str(font_path), size)
        except:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0,0), text, font=font)
        if (bbox[2]-bbox[0]) <= usable_w:
            # Check height with wrapping
            # Simple wrap by words
            words = text.split()
            lines = []
            cur = ""
            for w in words:
                test = f"{cur} {w}".strip()
                tb = draw.textbbox((0,0), test, font=font)
                if (tb[2]-tb[0]) <= usable_w:
                    cur = test
                else:
                    if cur:
                        lines.append(cur)
                    cur = w
            if cur:
                lines.append(cur)
            total_h = len(lines) * (bbox[3]-bbox[1] + 10)
            if total_h <= H * 0.6:
                break
        size -= 4
    
    font = ImageFont.truetype(str(font_path), size) if font_path.exists() else ImageFont.load_default()
    
    # Wrap text
    words = text.split()
    lines = []
    cur = ""
    for w in words:
        test = f"{cur} {w}".strip()
        tb = draw.textbbox((0,0), test, font=font)
        if (tb[2]-tb[0]) <= usable_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    
    # Measure total block
    line_heights = []
    max_w = 0
    for line in lines:
        bb = draw.textbbox((0,0), line, font=font)
        line_heights.append(bb[3]-bb[1])
        max_w = max(max_w, bb[2]-bb[0])
    
    total_h = sum(line_heights) + (len(lines)-1)*12
    start_y = (H - total_h)//2
    start_x = (W - max_w)//2
    
    # Glow behind text - soft light
    glow = Image.new("L", (W, H), 0)
    g_draw = ImageDraw.Draw(glow)
    g_draw.ellipse([W//2 - 300, H//2 - 200, W//2 + 300, H//2 + 200], fill=80)
    glow = glow.filter(ImageFilter.GaussianBlur(100))
    img = Image.composite(Image.new("RGB", (W, H), (40,42,60)), img, glow)
    draw = ImageDraw.Draw(img)
    
    # Draw each line with stroke + shadow (premium)
    y = start_y
    for i, line in enumerate(lines):
        bb = draw.textbbox((0,0), line, font=font)
        lw = bb[2]-bb[0]
        x = (W - lw)//2
        
        # Shadow
        draw.text((x+4, y+4), line, font=font, fill=(0,0,0,180), stroke_width=8, stroke_fill=(0,0,0,180))
        # Stroke + white
        draw.text((x, y), line, font=font, fill=(245,245,240), stroke_width=6, stroke_fill=(0,0,0,255))
        
        y += line_heights[i] + 12
    
    # Premium double line above first line
    if lines:
        rule_y = start_y - 30
        draw.rectangle([(W//2 - max_w//2 - 10, rule_y), (W//2 + max_w//2 + 10, rule_y+2)], fill=(180,182,200))
    
    img.save(output_path, quality=95)
    return output_path

def render_talking_caption(
    text: str,
    output_path: Path,
    *,
    config=None,
) -> Path:
    """
    Talking to viewers - Khand Bold with pill + stroke + shadow
    Your words: "texts when we have to share things or talking to viewers"
    """
    Image, ImageDraw, ImageFilter, ImageFont = _pil()
    
    text = " ".join((text or "").split())
    if not text:
        raise ValueError("caption needs text")
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    font_path = Path(__file__).parent.parent.parent / "assets" / "fonts" / "Khand-Bold.ttf"
    
    # Measure
    size = 150  # over_footage size
    # Hindi needs 15% bigger
    if any('\u0900' <= c <= '\u097F' for c in text):
        size = int(size * 1.15)
    
    try:
        font = ImageFont.truetype(str(font_path), size)
    except:
        font = ImageFont.load_default()
    
    probe = Image.new("L", (8,8))
    bbox = ImageDraw.Draw(probe).textbbox((0,0), text, font=font, stroke_width=8)
    gw, gh = bbox[2]-bbox[0], bbox[3]-bbox[1]
    
    pad = 32
    pill_pad = 18
    shadow_off = 6
    W = gw + pad*2 + shadow_off*2 + pill_pad*2
    H = gh + pad*2 + shadow_off*2 + pill_pad*2
    
    base = Image.new("RGBA", (W, H), (0,0,0,0))
    draw = ImageDraw.Draw(base)
    
    # Pill background 60% black rounded 24px
    try:
        draw.rounded_rectangle([pill_pad, pill_pad, W-pill_pad, H-pill_pad], radius=24, fill=(0,0,0,160))
    except:
        draw.rectangle([pill_pad, pill_pad, W-pill_pad, H-pill_pad], fill=(0,0,0,160))
    
    x = pad - bbox[0] + shadow_off//2
    y = pad - bbox[1] + shadow_off//2
    
    # Shadow
    shadow = Image.new("RGBA", (W, H), (0,0,0,0))
    s_draw = ImageDraw.Draw(shadow)
    s_draw.text((x+shadow_off, y+shadow_off), text, font=font, fill=(0,0,0,200), stroke_width=8, stroke_fill=(0,0,0,200))
    shadow = shadow.filter(ImageFilter.GaussianBlur(3))
    
    # Text white 255 with black stroke 8
    text_layer = Image.new("RGBA", (W, H), (0,0,0,0))
    t_draw = ImageDraw.Draw(text_layer)
    t_draw.text((x, y), text, font=font, fill=(255,255,255,255), stroke_width=8, stroke_fill=(0,0,0,255))
    
    combined = Image.alpha_composite(base, shadow)
    combined = Image.alpha_composite(combined, text_layer)
    
    combined.save(output_path, "PNG")
    return output_path
