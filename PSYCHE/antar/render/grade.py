"""
ANTAR - the look.

This module exists because the footage cannot be trusted to look like one
video. It arrives from different cameras, at different exposures, in different
light. One clip is a bright desk, the next is a dark window. Cut them together
raw and it looks like a folder, not a film.

So every clip is measured, then corrected, then measured again:

  1. A frame is taken from the clip and its average brightness is read.
  2. The gamma that would bring that frame into ANTAR's night window is worked
     out from two measurements - not guessed, and not one fixed number for all
     footage, because a fixed number either leaves a dark clip black or turns a
     bright clip grey.
  3. It is measured again. If it landed in the window and kept enough shadow
     detail, that gamma is used for the whole shot.

Two things are checked at the same time, because both are rules:

  * no frame mostly black - the config's own blocking number, 55% of the frame
  * no pure black at all - pure #000000 is banned everywhere, so the grade
    lifts the floor off zero rather than leaving crushed blacks behind

The target window lives here rather than in the config on purpose: it was
measured from the footage, and Phase 5 is where a measured value belongs until
there is a reason to lock it.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import typekit

# Where a graded frame should sit, 0-255. These are the project's own locked
# numbers, not a taste call: the master plan's table says "thumbnail brightness
# mean 35-45 (of 255)" and the config locks the same 35/45 for cards and the
# thumbnail path, with a clip-slot floor of 30. Phase 5 first used a darker
# invented window (72-104); that was a made-up number sitting next to a locked
# one, so it is gone. Footage and cards now share one register.
NIGHT_TARGET = (35.0, 45.0)
NIGHT_MID = (NIGHT_TARGET[0] + NIGHT_TARGET[1]) / 2.0
GAMMA_MIN, GAMMA_MAX = 0.30, 2.20
SHIFT_MIN, SHIFT_MAX = -0.35, 0.35
GRADE_SATURATION = 0.94
GRADE_CONTRAST = 1.04
FLOOR_LIFT = 6.0 / 255.0      # 0 -> 6/255, so nothing in the render is #000000
PURE_BLACK_MAX_PCT = 0.5      # % of a frame allowed to be pure black
# The working margin under the locked 55% "no frame mostly black" rule. A
# frame at 54.9% would pass and be one clip away from failing, so the grade
# aims well inside the line and says so when it cannot get there.
BLACK_TARGET_MAX_PCT = 46.0
PROBE_W, PROBE_H = 270, 480
PROBE_SECONDS = 0.30


@dataclass
class Grade:
    gamma: float
    brightness: float
    mean: float
    black_pct: float
    pure_black_pct: float
    probes: int = 0
    samples: int = 1
    admitted: str = ""
    trail: list[str] = field(default_factory=list)

    def line(self) -> str:
        shift = f"  shift {self.brightness:+.2f}" if abs(self.brightness) > 0.001 else ""
        worst = f"  (worst of {self.samples} samples)" if self.samples > 1 else ""
        return (f"gamma {self.gamma:.2f}{shift}  brightness {self.mean:.0f}/255  "
                f"black {self.black_pct:.0f}%{worst}")


class GradeError(RuntimeError):
    """The look could not be solved."""


def _measure_file(path: Path) -> tuple[float, float, float]:
    """Average brightness, black share, pure-black share - read from a file."""
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


def measure(path: Path) -> tuple[float, float, float]:
    return _measure_file(Path(path))


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


# The four named grades the rotation may apply, keyed by name.
# Each is a small colour curve + saturation push tuned for the project's
# night window. None of them turn a black frame into white - they tint,
# not bleach.
#
# r_off / g_off / b_off are colorbalance shadow offsets in the [-1, 1]
# range. They DO NOT use the eq filter's rg/gg/bg channel-gain options,
# which are only in ffmpeg 8+; colorbalance works in every ffmpeg build
# since 2.6 and is what the project ships via imageio-ffmpeg.
GRADE_PRESETS: dict[str, dict[str, float]] = {
    # PREMIUM UPGRADE 2026-10-04: More saturation, punchier contrast, less muddy
    # Old values made premium clips look dark/gray. New values: cinematic premium
    "warm-amber":          {"saturation": 1.08, "contrast": 1.12,
                                  "r_off":  0.08, "g_off":  0.02, "b_off": -0.16},
    "cold-blue":            {"saturation": 1.06, "contrast": 1.13,
                                  "r_off": -0.16, "g_off": -0.02, "b_off":  0.12},
    "neutral-grey-green":  {"saturation": 1.02, "contrast": 1.10,
                                  "r_off": -0.02, "g_off":  0.04, "b_off": -0.02},
    "desaturated-teal":    {"saturation": 0.92, "contrast": 1.14,
                                  "r_off": -0.10, "g_off":  0.06, "b_off":  0.08},
}


def _grade_preset(name: str) -> dict[str, float]:
    """Look up a preset, fall back to neutral if the name is unknown."""
    return GRADE_PRESETS.get(name, GRADE_PRESETS["neutral-grey-green"])


def _grade_filters(gamma: float, width: int, height: int, fps: int,
                   grain: bool = True, brightness: float = 0.0,
                   grade_name: str = "neutral-grey-green") -> str:
    """The whole look, as one filter string: frame, colour, floor, grain."""
    preset = _grade_preset(grade_name)
    chain = [
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}",
        f"fps={fps}",
        f"eq=gamma={gamma:.4f}:brightness={brightness:.4f}:"
        f"saturation={preset['saturation']:.4f}:"
        f"contrast={preset['contrast']:.4f}",
        f"colorbalance=rs={preset['r_off']:+.4f}:"
        f"gs={preset['g_off']:+.4f}:"
        f"bs={preset['b_off']:+.4f}",
        f"curves=all='0/{FLOOR_LIFT:.4f} 0.5/0.5 1/1'",
    ]
    if grain:
        chain.append("noise=alls=3:allf=t")      # hides the softness of upscales
    return ",".join(chain)


def _paste_overlay(frame: Path, overlay: tuple[str, int, int] | None) -> None:
    """Put the type on the probe frame, so what is measured is what is seen."""
    if not overlay:
        return
    from PIL import Image
    png, x, y = overlay
    with Image.open(frame) as base:
        canvas = base.convert("RGB")
        with Image.open(png) as layer:
            canvas.paste(layer.convert("RGBA"), (int(x), int(y)), layer.convert("RGBA"))
        canvas.save(frame, "PNG")


def _probe(ffmpeg: str, source: str, seek: float, gamma: float,
           brightness: float = 0.0,
           overlay: tuple[str, int, int] | None = None,
           grade_name: str = "neutral-grey-green") -> tuple[float, float, float]:
    """Encode a sliver at one setting and measure what actually came out."""
    out = Path(tempfile.gettempdir()) / f"antar_probe_{abs(hash((source, seek, gamma, brightness)))}.png"
    result = _run([ffmpeg, "-hide_banner", "-v", "error",
                   "-ss", f"{seek:.3f}", "-i", str(source),
                   "-vf", _grade_filters(gamma, PROBE_W, PROBE_H, 30,
                                         brightness=brightness,
                                         grade_name=grade_name),
                   "-frames:v", "1", "-y", str(out)])
    if result.returncode or not out.exists():
        raise GradeError(f"could not grade {Path(source).name}: "
                         f"{result.stderr.strip()[:160] or 'no frame came out'}")
    _paste_overlay(out, overlay)
    measured = _measure_file(out)
    out.unlink(missing_ok=True)
    return measured


def solve(ffmpeg: str, source: str, seek: float, *,
          target: tuple[float, float] = NIGHT_TARGET,
          trace: list[str] | None = None,
          overlay: tuple[str, int, int] | None = None,
          times: list[float] | None = None,
          grade_name: str = "neutral-grey-green") -> Grade:
    """
    Find the setting that puts this clip in the night window AND keeps it off
    "mostly black".

    Two locked rules are in play and they pull against each other on dark
    footage: the brightness band wants a mean under 45 of 255, the black rule
    wants no more than 55% of the frame under 16 of 255. On a dark interior
    both cannot always be met, and the old way of dealing with that was to
    report whichever number looked better. Here:

      * every candidate setting is measured at several points in the shot, not
        one, and the WORST of them is what has to pass
      * the best candidate found is kept, not the last one tried
      * if the two rules cannot both hold, the black rule wins - a mostly
        black frame is the fault that killed the earlier videos - and the
        conflict is written into the record instead of hidden
    """
    low, high = target
    mid = (low + high) / 2.0
    trail = trace if trace is not None else []
    sample_times = list(times) if times else [seek]
    probes = 0

    def take(gamma: float, brightness: float = 0.0) -> tuple[float, float, float]:
        """Worst mean, worst black, worst pure black across the samples."""
        nonlocal probes
        probes += 1
        worst_mean, worst_black, worst_pure = 255.0, 0.0, 0.0
        for at in sample_times:
            measured = _probe(ffmpeg, source, at, gamma, brightness, overlay,
                              grade_name=grade_name)
            worst_mean = min(worst_mean, measured[0])
            worst_black = max(worst_black, measured[1])
            worst_pure = max(worst_pure, measured[2])
        shift = f", shift {brightness:+.2f}" if abs(brightness) > 0.001 else ""
        trail.append(f"gamma {gamma:.2f}{shift}{'' if len(sample_times) == 1 else f', {len(sample_times)} samples'}"
                     f" -> brightness {worst_mean:.0f}, black {worst_black:.0f}%, "
                     f"pure black {worst_pure:.2f}%")
        return worst_mean, worst_black, worst_pure

    def fits_in_band(measurement: tuple[float, float, float]) -> bool:
        return low <= measurement[0] <= high

    def clean_of_black(measurement: tuple[float, float, float]) -> bool:
        return (measurement[1] <= BLACK_TARGET_MAX_PCT
                and measurement[2] <= PURE_BLACK_MAX_PCT)

    def keeps_the_rules(measurement: tuple[float, float, float]) -> bool:
        return fits_in_band(measurement) and clean_of_black(measurement)

    candidates: list[Grade] = []

    def keep(gamma: float, brightness: float, measurement: tuple[float, float, float]) -> Grade:
        entry = Grade(gamma, brightness, *measurement, probes=probes,
                      samples=len(sample_times), trail=list(trail))
        candidates.append(entry)
        return entry

    first = take(1.0)
    if keeps_the_rules(first):
        return keep(1.0, 0.0, first)

    second_gamma = 0.60 if first[0] > high else 1.60
    second = take(second_gamma)

    def solve_from(g1: float, m1: float, g2: float, m2: float) -> float:
        """Brightness follows a power law in gamma closely enough to invert."""
        import math
        if m1 <= 0.5 or m2 <= 0.5 or m2 == m1:
            return min(max(1.0, GAMMA_MIN), GAMMA_MAX)
        exponent = math.log(m2 / m1) / math.log(g2 / g1)
        if abs(exponent) < 0.05:
            return min(max(g2, GAMMA_MIN), GAMMA_MAX)
        return min(max(g1 * (mid / m1) ** (1.0 / exponent), GAMMA_MIN), GAMMA_MAX)

    # aim at the upper half of the band: it gives the black rule the best chance
    aim = mid + (high - mid) * 0.5
    if first[0] > high:
        pair = ((1.0, first[0]), (second_gamma, second[0]))
    else:
        pair = ((second_gamma, second[0]), (1.0, first[0]))
    gamma = solve_from(pair[0][0], pair[0][1], pair[1][0], pair[1][1])

    measured = take(gamma)
    keep(gamma, 0.0, measured)
    if keeps_the_rules(measured):
        return candidates[-1]

    for _ in range(4):
        if keeps_the_rules(measured):
            break
        if not clean_of_black(measured):
            gamma = min(gamma * 1.15, GAMMA_MAX)      # lift until black comes off
        elif measured[0] < low:
            gamma = min(gamma * 1.12, GAMMA_MAX)
        else:
            gamma = max(gamma * 0.90, GAMMA_MIN)
        measured = take(gamma)
        keep(gamma, 0.0, measured)

    for entry in candidates:
        if keeps_the_rules((entry.mean, entry.black_pct, entry.pure_black_pct)):
            return entry

    # gamma has run out of room - a flat white frame stays white whatever the
    # gamma is, so the brightness term takes over, measured then solved.
    best = min(candidates, key=lambda e: (not clean_of_black((e.mean, e.black_pct, e.pure_black_pct)),
                                          abs(e.mean - mid)))
    # gamma cannot reach the band for this footage - the whites will not go
    # down and the blacks will not come up (a flat white frame stays white at
    # any gamma). The brightness term can, so it is solved the same way: one
    # measurement for the slope, then the offset worked out from it.
    if (not fits_in_band((best.mean, best.black_pct, best.pure_black_pct))
            or not clean_of_black((best.mean, best.black_pct, best.pure_black_pct))):
        step = -0.08 if best.mean > high else 0.06
        stepped = take(best.gamma, step)
        slope = (stepped[0] - best.mean) / step
        if abs(slope) >= 20.0:
            for _ in range(3):
                offset = getattr(best, "brightness", 0.0) + min(
                    max((mid - best.mean) / slope, SHIFT_MIN), SHIFT_MAX)
                measured = take(best.gamma, offset)
                keep(best.gamma, offset, measured)
                if keeps_the_rules(measured):
                    return candidates[-1]
                best = candidates[-1]

    for entry in candidates:
        if keeps_the_rules((entry.mean, entry.black_pct, entry.pure_black_pct)):
            return entry

    # The two rules cannot both hold on this footage. The black rule wins, and
    # the run says so by name.
    chosen = min(candidates, key=lambda e: (e.black_pct, abs(e.mean - mid)))
    inside = chosen.black_pct <= 55.0
    chosen.admitted = (
        f"dark footage: brightness {chosen.mean:.0f}/255 (band {low:.0f}-{high:.0f}) "
        f"keeps the black at {chosen.black_pct:.0f}% of the frame - "
        + ("inside the locked 55% limit, but above the safety margin this stage "
           "aims for" if inside else
           "OVER the locked 55% limit - this shot needs better footage"))
    return chosen


# ------------------------------------------------------------------- segments

def encode_clip(ffmpeg: str, source: str, out_path: Path, *,
                seek: float, seconds: float, gamma: float, brightness: float = 0.0,
                width: int, height: int, fps: int, crf: int, preset: str,
                popups: list[dict] | None = None,
                grade_name: str = "neutral-grey-green") -> None:
    """
    One shot, finished: graded, grained, and its words burnt on.

    The source is looped and then trimmed rather than seeked before the input,
    because a beat can be longer than what is left of a clip after the seek
    point - and a short segment is how a video drifts out of sync with its own
    voice.
    """
    popups = popups or []
    cmd = [ffmpeg, "-hide_banner", "-v", "error", "-stream_loop", "4",
           "-i", str(source), "-ss", f"{seek:.3f}"]

    for popup in popups:
        cmd += ["-loop", "1", "-framerate", str(fps), "-t", f"{seconds:.3f}",
                "-i", str(popup["path"])]

    chain = [f"[0:v]{_grade_filters(gamma, width, height, fps, brightness=brightness, grade_name=grade_name)}[base]"]
    last = "base"
    for index, popup in enumerate(popups, start=1):
        node = f"v{index}"
        chain.append(
            f"[{index}:v]format=rgba[p{index}];"
            f"[{last}][p{index}]overlay=x={popup['x']}:y={popup['y']}:"
            f"enable='between(t,{popup['start']:.3f},{popup['end']:.3f})'[{node}]")
        last = node

    cmd += ["-filter_complex", ";".join(chain), "-map", f"[{last}]",
            "-t", f"{seconds:.3f}", "-an",
            "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
            "-pix_fmt", "yuv420p", "-r", str(fps), "-y", str(out_path)]
    result = _run(cmd)
    if result.returncode:
        raise GradeError(f"the shot would not render: {result.stderr.strip()[:300]}")


def encode_card(ffmpeg: str, card_png: str, out_path: Path, *,
                seconds: float, width: int, height: int, fps: int,
                crf: int, preset: str, push: float = 0.055) -> None:
    """
    A text screen, given a slow push so it is not a frozen image.

    No grade is applied: the card was already drawn at the brightness the band
    asks for, in the picture stage, and it was measured there. Grading it again
    would move a number that was deliberately solved once.
    """
    push_chain = (
        f"scale=w='{width}*(1+{push}*t/{max(seconds, 0.1):.3f})':"
        f"h='{height}*(1+{push}*t/{max(seconds, 0.1):.3f})':eval=frame,"
        f"crop={width}:{height},fps={fps},format=yuv420p")
    cmd = [ffmpeg, "-hide_banner", "-v", "error",
           "-loop", "1", "-framerate", str(fps), "-t", f"{seconds:.3f}",
           "-i", str(card_png), "-vf", push_chain,
           "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
           "-pix_fmt", "yuv420p", "-r", str(fps), "-y", str(out_path)]
    result = _run(cmd)
    if result.returncode:
        raise GradeError(f"the text screen would not render: {result.stderr.strip()[:300]}")


def concat_and_mux(ffmpeg: str, segments: list[Path], list_path: Path,
                   audio: str | None, out_path: Path, seconds: float) -> list[str]:
    """
    Join the shots and lay the mastered voice under them.

    The video is copied, not re-encoded: every shot was already encoded at the
    one size, frame rate and pixel format, so joining them costs nothing and
    loses nothing. The voice is encoded once, to what the platform takes.
    """
    list_path.write_text(
        "".join(f"file '{Path(seg).resolve()}'\n" for seg in segments), encoding="utf-8")

    cmd = [ffmpeg, "-hide_banner", "-v", "error", "-f", "concat", "-safe", "0",
           "-i", str(list_path)]
    if audio:
        cmd += ["-i", str(audio)]
    cmd += ["-map", "0:v"]
    if audio:
        cmd += ["-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
        if seconds > 0:
            cmd += ["-t", f"{seconds:.3f}"]
    cmd += ["-c:v", "copy", "-movflags", "+faststart", "-y", str(out_path)]
    result = _run(cmd)
    if result.returncode:
        raise GradeError(f"the shots would not join: {result.stderr.strip()[:300]}")
    return cmd


def probe_video(ffmpeg: str, path: Path) -> dict:
    """What is actually in the finished file, read from the file."""
    result = _run([ffmpeg, "-hide_banner", "-i", str(path), "-f", "null", "-"])
    text = result.stderr
    info: dict = {"file": str(path), "bytes": Path(path).stat().st_size if Path(path).exists() else 0}

    import re
    match = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", text)
    if match:
        info["seconds"] = (int(match.group(1)) * 3600 + int(match.group(2)) * 60
                           + float(match.group(3)))
    match = re.search(r"Video:\s*([a-z0-9]+).*?(\d{2,5})x(\d{2,5})", text)
    if match:
        info["codec"] = match.group(1)
        info["width"], info["height"] = int(match.group(2)), int(match.group(3))
    match = re.search(r"(\d+(?:\.\d+)?)\s*fps", text)
    if match:
        info["fps"] = float(match.group(1))
    match = re.search(r"Audio:\s*([a-z0-9]+).*?(\d+)\s*Hz,\s*([a-z]+)", text)
    if match:
        info["audio_codec"] = match.group(1)
        info["audio_hz"] = int(match.group(2))
        info["audio_channels"] = match.group(3)
    info["streams_json"] = ""
    return info


def scan_frames(ffmpeg: str, path: Path, *, every: float = 1.0,
                width: int = 270, height: int = 480) -> list[dict]:
    """
    Walk the finished video a second at a time and measure every frame.

    This is the proof for 'no frame mostly black' - not a promise, a table.
    """
    rows: list[dict] = []
    seconds = probe_video(ffmpeg, path).get("seconds", 0.0)
    step = every
    at = 0.0
    out = Path(tempfile.gettempdir()) / "antar_scan.png"
    while at < seconds:
        result = _run([ffmpeg, "-hide_banner", "-v", "error", "-ss", f"{at:.3f}",
                       "-i", str(path), "-vf", f"scale={width}:{height}",
                       "-frames:v", "1", "-y", str(out)])
        if result.returncode or not out.exists():
            break
        mean, black, pure = _measure_file(out)
        rows.append({"at": round(at, 3), "mean": round(mean, 1),
                     "black_pct": round(black, 1), "pure_black_pct": round(pure, 2)})
        at += step
    out.unlink(missing_ok=True)
    return rows


def peak_in(path: Path, box: tuple[int, int, int, int] | None = None) -> float:
    """The brightest pixel in a frame, or in a box of it."""
    from PIL import Image

    with Image.open(path) as image:
        grey = image.convert("L")
        if box:
            grey = grey.crop(box)
        return float(max(grey.getextrema()))
