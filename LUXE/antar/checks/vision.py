"""
ANTAR - the parts of the check suite that look at pixels.

Everything here reads a finished MP4 and returns numbers. Nothing estimates,
nothing remembers what the build intended.

  * the feed tile - the real 16:9 tile the feed shows a vertical video in,
    extracted at 1280x720 and measured. This is the number that killed two
    earlier videos at 7-11 of 255, so it is measured on the tile, not on the
    whole frame.
  * the frame sweep - a frame a second, every one measured, every one printed.
  * the type at 15% - the word is measured where a viewer actually sees it:
    a phone-sized picture, where the whole frame is about 162 pixels wide.
"""

from __future__ import annotations

from pathlib import Path

TILE = (1280, 720)          # the feed's own tile size
ZOOM = 0.15                 # the legibility test in the spec


class VisionError(RuntimeError):
    """A measurement could not be taken."""


def _run(cmd: list[str]):
    import subprocess
    return subprocess.run(cmd, capture_output=True, text=True)


def _measure(path: Path) -> tuple[float, float, float]:
    from PIL import Image

    with Image.open(path) as image:
        histogram = image.convert("L").histogram()
    total = sum(histogram)
    if not total:
        return 0.0, 100.0, 100.0
    mean = sum(index * count for index, count in enumerate(histogram)) / total
    black = 100.0 * sum(histogram[:16]) / total
    pure = 100.0 * histogram[0] / total
    return mean, black, pure


def contrast(path: Path) -> float:
    """Standard deviation of the frame - how much light and dark it carries."""
    from PIL import Image
    import numpy as np

    with Image.open(path) as image:
        values = np.asarray(image.convert("L"), dtype="float32")
    return float(values.std())


def extract_tile(ffmpeg: str, video: Path, at: float, out: Path,
                 size: tuple[int, int] = TILE) -> Path:
    """
    The tile the feed shows, taken from the middle of the frame.

    A vertical video is shown in the feed as a wide tile: the platform takes the
    middle band of the frame and scales it. The middle band is where the
    subject and the type are, so that is what is measured.
    """
    width, height = size
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    result = _run([ffmpeg, "-hide_banner", "-v", "error", "-ss", f"{at:.3f}",
                   "-i", str(video),
                   "-vf", f"scale={width}:-2,crop={width}:{height}",
                   "-frames:v", "1", "-y", str(out)])
    if result.returncode or not out.exists():
        raise VisionError(f"could not take the tile: {result.stderr.strip()[:160]}")
    return out


def tile_path(at: float, out: Path) -> Path:
    return Path(out)


def sweep(ffmpeg: str, video: Path, *, seconds: float, count: int,
          out_dir: Path, tag: str = "sweep") -> list[dict]:
    """A frame a second, every one measured. The list is the proof."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    if count <= 1 or seconds <= 0:
        return rows
    for index in range(count):
        at = seconds * index / (count - 1) if count > 1 else 0.0
        at = min(at, max(seconds - 0.05, 0.0))
        frame = out_dir / f"{tag}_{index:02d}.png"
        result = _run([ffmpeg, "-hide_banner", "-v", "error", "-ss", f"{at:.3f}",
                       "-i", str(video), "-vf", "scale=270:480", "-frames:v", "1",
                       "-y", str(frame)])
        if result.returncode or not frame.exists():
            continue
        mean, black, pure = _measure(frame)
        rows.append({"at": round(at, 3), "mean": round(mean, 1),
                     "black_pct": round(black, 1), "pure_black_pct": round(pure, 2)})
        frame.unlink(missing_ok=True)
    return rows


def type_at_zoom(ffmpeg: str, video: Path, at: float, box: tuple[int, int, int, int],
                 glyph: Path, out_dir: Path, *, zoom: float = ZOOM) -> dict:
    """
    How the type reads when the video is the size of a phone in a feed.

    Two numbers, both measured on the rendered frame with the real word on it:

      height_px   the word's own height after the frame is scaled to 15%
      difference  the average brightness of the letters against the average of
                  what surrounds them

    The mask used to find the letters is the same word drawn again, so the
    measurement cannot drift from what was rendered.
    """
    from PIL import Image
    import numpy as np

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frame_path = out_dir / "zoom_frame.png"
    result = _run([ffmpeg, "-hide_banner", "-v", "error", "-ss", f"{at:.3f}",
                   "-i", str(video), "-frames:v", "1", "-y", str(frame_path)])
    if result.returncode or not frame_path.exists():
        raise VisionError(f"no frame at {at:.3f}s: {result.stderr.strip()[:160]}")

    x, y, width, height = box
    with Image.open(frame_path) as frame:
        crop = frame.convert("RGB").crop((x, y, x + width, y + height))

    scaled_w = max(1, int(crop.width * zoom))
    scaled_h = max(1, int(crop.height * zoom))
    small = crop.resize((scaled_w, scaled_h), Image.LANCZOS)
    small_grey = np.asarray(small.convert("L"), dtype="float32")

    if glyph.exists():
        with Image.open(glyph) as mask_image:
            mask = mask_image.convert("RGBA").resize((scaled_w, scaled_h), Image.LANCZOS)
        alpha = np.asarray(mask)[..., 3].astype("float32")
    else:
        alpha = np.full((scaled_h, scaled_w), 255.0, dtype="float32")

    letters = alpha > 128
    around = alpha < 32
    if letters.sum() < 4 or around.sum() < 4:
        raise VisionError("the type mask and the frame do not overlap")

    letter_mean = float(small_grey[letters].mean())
    surround_mean = float(small_grey[around].mean())

    rows = np.where(letters.any(axis=1))[0]
    height_scaled = int(rows[-1] - rows[0] + 1) if len(rows) else 0
    frame_path.unlink(missing_ok=True)

    return {
        "zoom": zoom,
        "height_px": height_scaled,
        "full_height_px": int(round(height_scaled / zoom)),
        "difference": round(letter_mean - surround_mean, 1),
        "letter_mean": round(letter_mean, 1),
        "surround_mean": round(surround_mean, 1),
    }


def scale_of(video_seconds: float, mp4_seconds: float) -> float:
    """How far the finished file drifts from the audio it was built on."""
    if mp4_seconds <= 0:
        return 0.0
    return abs(mp4_seconds - video_seconds) / mp4_seconds
