"""
LUXE panel - the manual thumbnail.

The spec says the thumbnail is automatic, from the brightest compliant second,
**with a manual override in the panel, always**. This is that override.

It does one thing and says exactly what it did: cut the frame at the second the
operator asked for, measure it the same way the check suite measures the
opening frame, save it as `<render>_manual.jpg`, and report the number. If the
number is outside the locked 35-45 band the frame is still saved - a person
asked for it - but the panel says so, and the check suite will say so too.
"""

from __future__ import annotations

from pathlib import Path

from ..vault import find_ffmpeg


class ThumbError(RuntimeError):
    """The frame could not be cut, and here is why."""


def manual(config, render_id: str, second: float, video: Path | None = None) -> dict:
    """
    Cut the frame the operator asked for, save it, measure it, and record it.

    Three things make the panel's number and the check's number the same number:

      * the frame is saved as a real image at the video's own size, 1080x1920;
      * the brightness is measured **on the saved file** with the same helper
        the check suite uses for a thumbnail image;
      * the file's path is written into the details file, which is the first
        thing the check looks for - "an image made for the job beats a frame
        that happened to be first".

    So a manual pick is not a decoration the check ignores. It becomes the
    thumbnail the check grades.
    """
    from ..checks import vision
    from . import data

    video = video or data.video_path(config, render_id)
    if not video or not Path(video).exists():
        raise ThumbError(
            f"there is no {render_id}.mp4 in output/video to take a frame from. "
            "Videos are delivered in LUXE_VIDEOS.zip and deleted from the "
            "workshop - extract it, or build the video again, and the panel can "
            "cut a thumbnail.")
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise ThumbError("no ffmpeg available - run INSTALL.bat")

    second = max(0.0, float(second))
    folder = config.path("paths.output") / "thumbs"
    folder.mkdir(parents=True, exist_ok=True)
    final = folder / f"{render_id}_manual.jpg"
    temporary = folder / f"{render_id}_manual.tmp.jpg"

    width, height = _canvas(config)
    result = _cut(ffmpeg, Path(video), second, temporary,
                  f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                  f"crop={width}:{height}")
    if result.returncode or not temporary.exists():
        raise ThumbError(f"the frame could not be cut: {result.stderr.strip()[:160]}")
    temporary.replace(final)

    mean, black, pure = vision._measure(final)
    contrast = vision.contrast(final)
    low = float(config.get("thresholds.thumbnail_brightness_min", 35))
    high = float(config.get("thresholds.thumbnail_brightness_max", 45))
    in_band = low <= mean <= high

    recorded = _record(config, render_id, final, second, mean, in_band)
    return {
        "path": str(final),
        "second": second,
        "mean": round(mean, 1),
        "contrast": round(contrast, 1),
        "black_pct": round(black, 1),
        "pure_black_pct": round(pure, 1),
        "band": [low, high],
        "in_band": in_band,
        "recorded_in_details": recorded,
        "note": ("inside the locked band" if in_band else
                 f"outside the locked band {low:.0f}-{high:.0f} - this frame is "
                 f"saved and the choice stays yours, but the check suite will "
                 f"flag it, because the check now grades this image"),
        "render_id": render_id,
    }


def _canvas(config) -> tuple[int, int]:
    width = int(config.get("canvas.width", 1080))
    height = int(config.get("canvas.height", 1920))
    return width, height


def _cut(ffmpeg: str, video: Path, second: float, out: Path, filters: str):
    """
    One frame, at the operator's second.

    `-ss` goes before `-i`: at 12 seconds into a file this is the difference
    between decoding twelve seconds and seeking straight there.
    """
    import subprocess

    return subprocess.run(
        [ffmpeg, "-hide_banner", "-v", "error", "-ss", f"{second:.3f}", "-i", str(video),
         "-vf", filters, "-frames:v", "1", "-q:v", "3", "-y", str(out)],
        capture_output=True, text=True)


def _record(config, render_id: str, path: Path, second: float, mean: float,
            in_band: bool) -> bool:
    """
    Write the pick into the details file, so the check grades this image.

    Returns True when it was written, False when there is no details file yet -
    a person may pick a thumbnail before the details stage has run, and the
    frame still gets saved.
    """
    import time

    from ..details import write as write_details
    from . import data

    details_path = config.path("paths.output") / "details" / f"{render_id}_details.json"
    payload = data._read(details_path)
    if not payload:
        return False
    payload["thumbnail_path"] = str(path)
    payload["thumbnail_manual"] = True
    payload["thumbnail"] = dict(payload.get("thumbnail") or {})
    payload["thumbnail"].update({
        "at": second, "mean": round(mean, 1), "in_band": in_band,
        "reason": "picked by hand in the panel",
    })
    payload["edited_by_hand"] = True
    payload["edited_at"] = time.time()
    write_details(config, render_id, payload)
    return True
