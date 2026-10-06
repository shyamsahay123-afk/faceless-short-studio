"""
ANTAR - the build stage. The plan becomes a finished MP4.

What happens here, in order:

  1. every beat's picture is graded to the house look and corrected by
     measurement (see grade.py)
  2. the measured words are cut into one and two word popups and burnt onto
     the picture, inside the safe zones, in Khand
  3. the shots are joined - video copied, not re-encoded - and the mastered
     voice is laid underneath
  4. the finished file is opened again and measured: resolution, frame rate,
     duration, the black share of every second of it, the type's brightest
     pixel, and a face scan of the render itself

Step 4 is the point. A build that says it is done without looking at its own
output is how a broken video reaches an upload button.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .. import log
from . import grade as grading
from . import typekit


class BuildError(RuntimeError):
    """The build stopped."""


@dataclass
class BuiltShot:
    index: int
    kind: str
    object_hi: str
    start: float
    end: float
    hold: float
    segment: Path
    look: str = ""
    popups: list[typekit.Chunk] = field(default_factory=list)
    grade: grading.Grade | None = None

    def line(self) -> str:
        return (f"beat {self.index}  {self.kind:4}  {self.object_hi:10} "
                f"{self.start:5.1f}-{self.end:5.1f}s  {self.look}")


def latest_plan(config) -> Path | None:
    plans = sorted((config.path("paths.output") / "plans").glob("*_picture.json"))
    return plans[-1] if plans else None


def load_plan(config, path: Path | None = None) -> dict:
    chosen = Path(path) if path else latest_plan(config)
    if not chosen or not Path(chosen).exists():
        raise BuildError("no picture plan on file - run: python run.py picture")
    try:
        return json.loads(Path(chosen).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BuildError(f"the plan on file is damaged: {chosen}") from exc


def _ffmpeg() -> str:
    from ..vault import find_ffmpeg

    path = find_ffmpeg()
    if not path:
        raise BuildError("no ffmpeg available - run INSTALL.bat (it installs "
                         "imageio-ffmpeg, which brings its own copy)")
    return path


def _plan_popups(config, shot: dict, words: list[dict], render_id: str,
                 popups_dir: Path) -> list[dict]:
    """
    The popups for one shot, in the shot's own time, already placed.

    A text screen needs no popup: the card already carries its word at 250px
    in the middle of the frame. Burning the spoken words over it as well would
    be two titles fighting on one screen.
    """
    if (shot.get("kind") or "clip") != "clip":
        return []

    chunks = typekit.chunk_words(words, float(shot["start"]), float(shot["end"]))
    placed: list[dict] = []
    for number, chunk in enumerate(chunks):
        safe_name = "".join(c for c in chunk.text if c.isalnum())[:14] or "pop"
        png = popups_dir / f"{render_id}_{shot['index']:02d}_{number:02d}_{safe_name}.png"
        popup = typekit.render_popup(chunk.text, png, config)
        x, y = typekit.place(config, popup.width, popup.height)
        placed.append({
            "path": png, "x": x, "y": y, "size": popup.size,
            "text": chunk.text,
            "start": round(chunk.start - float(shot["start"]), 3),   # shot-local
            "end": round(chunk.end - float(shot["start"]), 3),
            "global_start": chunk.start, "global_end": chunk.end,
            "box": [x, y, popup.width, popup.height],
        })
    return placed


def build(config, plan: dict, *, progress=None, keep_parts: bool = False,
          audio: Path | None = None) -> dict:
    """Render the plan. Returns everything that was done, measured."""
    say = progress or (lambda message: log.info(message))

    ffmpeg = _ffmpeg()
    render_id = plan.get("render_id") or "ANTAR_0000"
    shots = plan.get("shots") or []
    if not shots:
        raise BuildError("the plan has no shots in it")

    width = int(config.get("canvas.width", 1080))
    height = int(config.get("canvas.height", 1920))
    fps = int(config.get("build.fps", 30))
    crf = int(config.get("build.crf", 18))
    preset = str(config.get("build.preset", "medium"))

    out_dir = config.path("paths.output") / "video"
    parts_dir = out_dir / "_parts" / render_id
    popups_dir = out_dir / "popups" / render_id
    for folder in (out_dir, parts_dir, popups_dir):
        folder.mkdir(parents=True, exist_ok=True)

    voice = _voice_for(config, render_id)
    if audio is None:
        audio = Path(voice["track"]["path"]) if voice else None
    if audio and not Path(audio).exists():
        audio = None
    words = (voice or {}).get("word_timings") or []
    if voice:
        say(f"the voice: {voice['track']['seconds']:.2f}s of mastered audio, "
            f"{len(words)} word times")

    built: list[BuiltShot] = []
    for shot in shots:
        index = int(shot["index"])
        kind = (shot.get("kind") or "clip").lower()
        start, end = float(shot["start"]), float(shot["end"])
        hold = float(shot.get("hold") or (end - start))
        segment = parts_dir / f"seg_{index:02d}.mp4"
        popups = _plan_popups(config, shot, words, render_id, popups_dir)

        if kind == "clip":
            seek = max(0.0, min(float(shot.get("seconds") or 0) * 0.25, 1.5))
            # The bright word sitting on the frame is part of the frame, so the
            # grade is solved with the type on it - the longest piece of type in
            # this shot, at the place it will actually sit.
            longest = max(popups, key=lambda p: p["end"] - p["start"], default=None)
            overlay = (str(longest["path"]), longest["box"][0], longest["box"][1]) if longest else None
            # measured at three points across the shot, not one: a clip can be
            # bright at the start and nearly black two seconds later.
            marks = [0.12, 0.5, 0.88]
            sample_times = [min(float(shot.get("seconds") or 9.0) * 0.9,
                                seek + max(0.0, hold * mark - 0.4))
                            for mark in marks]
            if overlay:
                sample_times[1] = seek + (longest["start"] + longest["end"]) / 2.0
                solved = grading.solve(ffmpeg, shot["path"], sample_times[1],
                                       overlay=overlay, times=sample_times,
                                       grade_name=shot.get("grade_name", "neutral-grey-green"))
            else:
                solved = grading.solve(ffmpeg, shot["path"], seek, times=sample_times,
                                       grade_name=shot.get("grade_name", "neutral-grey-green"))
            grading.encode_clip(ffmpeg, shot["path"], segment, seek=seek,
                                seconds=hold, gamma=solved.gamma,
                                brightness=solved.brightness, width=width,
                                height=height, fps=fps, crf=crf, preset=preset,
                                popups=popups,
                                grade_name=shot.get("grade_name", "neutral-grey-green"))
            look = solved.line()
            entry = BuiltShot(index, kind, shot.get("object_hi", ""), start, end,
                              hold, segment, look, popups, solved)
        else:
            grading.encode_card(ffmpeg, shot["path"], segment, seconds=hold,
                                width=width, height=height, fps=fps, crf=crf,
                                preset=preset)
            mean, black, pure = grading.measure(Path(shot["path"]))
            entry = BuiltShot(index, kind, shot.get("object_hi", ""), start, end,
                              hold, segment,
                              f"text screen  brightness {mean:.0f}/255  "
                              f"black {black:.0f}%", popups, None)
        built.append(entry)
        say(entry.line() + (f"   {len(popups)} popup(s)" if popups else ""))
        if entry.grade and entry.grade.admitted:
            say(f"        admitted: {entry.grade.admitted}")

    total = sum(entry.hold for entry in built)
    finished = out_dir / f"{render_id}.mp4"
    seconds = float((voice or {}).get("track", {}).get("seconds") or total)
    grading.concat_and_mux(ffmpeg, [entry.segment for entry in built],
                           parts_dir / "segments.txt",
                           str(audio) if audio else None, finished, seconds)
    say(f"joined {len(built)} shots -> {finished.name}")

    verification = verify(config, finished, built, ffmpeg=ffmpeg)
    framed = contact_sheet(ffmpeg, finished, built, out_dir, render_id)

    if not keep_parts:
        shutil.rmtree(parts_dir, ignore_errors=True)

    record = {
        "render_id": render_id,
        "file": str(finished),
        "seconds": seconds,
        "shots": len(built),
        "popups": sum(len(entry.popups) for entry in built),
        "audio": str(audio) if audio else None,
        "look": {
            "target": list(grading.NIGHT_TARGET),
            "grades": [{"index": entry.index,
                        "admitted": entry.grade.admitted if entry.grade else "",
                        "gamma": round(entry.grade.gamma, 3) if entry.grade else None,
                        "shift": round(entry.grade.brightness, 3) if entry.grade else None,
                        "brightness": round(entry.grade.mean, 1) if entry.grade else None,
                        "black_pct": round(entry.grade.black_pct, 1) if entry.grade else None,
                        "probes": entry.grade.probes if entry.grade else 0}
                       for entry in built],
        },
        "type": [{"beat": entry.index, "text": popup["text"], "size": popup["size"],
                  "box": popup["box"], "start": popup["global_start"],
                  "end": popup["global_end"]}
                 for entry in built for popup in entry.popups],
        "checks": verification["checks"],
        "frames": verification["frames"],
        "sheet": str(framed),
    }
    write_json(out_dir / f"{render_id}_build.json", record)
    return record


def _voice_for(config, render_id: str) -> dict | None:
    path = config.path("paths.output") / "audio" / f"{render_id}_audio.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    temporary.replace(path)
    return path


# --------------------------------------------------------------- verification

def verify(config, video: Path, built: list[BuiltShot], *, ffmpeg: str) -> dict:
    """
    Open the finished file and measure it. Every number below comes from the
    MP4, not from the intentions that produced it.
    """
    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "pass": bool(passed), "detail": detail})

    info = grading.probe_video(ffmpeg, video)
    width = int(config.get("canvas.width", 1080))
    height = int(config.get("canvas.height", 1920))

    check("the file exists and is not empty", video.exists() and info["bytes"] > 0,
          f"{video.name}  {info['bytes'] / 1_048_576:.1f} MB")
    check("the canvas is the locked size",
          info.get("width") == width and info.get("height") == height,
          f"{info.get('width')}x{info.get('height')} (locked {width}x{height})")
    check("the frame rate is the build rate", info.get("fps") == 30.0,
          f"{info.get('fps')} fps")
    check("the voice is inside the file",
          info.get("audio_codec") == "aac" and info.get("audio_hz") == 48000,
          f"{info.get('audio_codec')} {info.get('audio_hz')}Hz")

    measured_seconds = float(info.get("seconds") or 0.0)
    wanted = sum(entry.hold for entry in built)
    check("the shots add up to the plan",
          abs(measured_seconds - wanted) <= 0.12,
          f"{measured_seconds:.2f}s in the file, {wanted:.2f}s of shots")

    scan = grading.scan_frames(ffmpeg, video, every=1.0)
    worst_black = max((row["black_pct"] for row in scan), default=0.0)
    limit = float(config.get("thresholds.darkest_frame_max_black_pct", 55))
    check("no frame is mostly black (locked rule)", worst_black <= limit,
          f"darkest second {worst_black:.0f}% black (limit {limit:.0f}%)")

    darkest = min((row["mean"] for row in scan), default=0.0)
    means = sorted(row["mean"] for row in scan) or [0.0]
    floor = float(config.get("thresholds.clip_slot_brightness_min", 30))
    low = float(config.get("thresholds.thumbnail_brightness_min", 35))
    high = float(config.get("thresholds.thumbnail_brightness_max", 45))
    opening = next((row["mean"] for row in scan if row["at"] <= 0.6), means[0])
    check("no second falls under the clip-slot floor (locked rule)", darkest >= floor,
          f"darkest second {darkest:.0f}/255 (floor {floor:.0f})")
    check("the opening tile sits in the locked brightness band (locked rule)",
          low <= opening <= high,
          f"opening second {opening:.0f}/255 in band {low:.0f}-{high:.0f} "
          f"(whole video {darkest:.0f}-{max(means):.0f})")

    pure_worst = max((row["pure_black_pct"] for row in scan), default=0.0)
    check("no pure black in the render (locked rule)", pure_worst <= 2.0,
          f"worst pure-black share {pure_worst:.2f}%")

    boxes_ok, boxes_note = _boxes_inside(config, built)
    check("every popup sits inside the safe zones", boxes_ok, boxes_note)

    typed = _type_pixels(ffmpeg, video, built, video.parent)
    check("the type is bright enough to read and never pure white",
          typed["ok"], typed["note"])

    faces = _face_scan(ffmpeg, video, video.parent)
    check("no faces in the finished render", faces["count"] == 0, faces["note"])

    seam = _loop_rhyme(ffmpeg, video, video.parent)
    check("the last frame rhymes with the first", seam["difference"] <= 40.0,
          f"first-to-last difference {seam['difference']:.0f}/255 (lower is closer)")

    return {"info": info, "checks": checks, "frames": scan, "sheet": None}


def _boxes_inside(config, built: list[BuiltShot]) -> tuple[bool, str]:
    width = int(config.get("canvas.width", 1080))
    height = int(config.get("canvas.height", 1920))
    safe_top = int(config.get("canvas.safe_zones.top_px", 220))
    safe_bottom = int(config.get("canvas.safe_zones.bottom_px", 420))

    checked = 0
    for entry in built:
        for popup in entry.popups:
            x, y, w, h = popup["box"]
            if x < 0 or x + w > width or y < safe_top or y + h > height - safe_bottom:
                return False, (f"popup {popup['text']!r} at {popup['box']} leaves the "
                               f"safe zones ({safe_top}..{height - safe_bottom} tall)")
            checked += 1
    return True, f"{checked} popup(s) checked against {safe_top}px top / {safe_bottom}px bottom"


def _type_pixels(ffmpeg: str, video: Path, built: list[BuiltShot],
                 folder: Path) -> dict:
    """Look at the frame a popup is on, and read the type's own pixels."""
    from .grade import peak_in

    for entry in built:
        for popup in entry.popups:
            middle = (popup["start"] + popup["end"]) / 2.0
            frame = folder / f"type_probe_{entry.index:02d}.png"
            result = grading._run([ffmpeg, "-hide_banner", "-v", "error",
                                   "-ss", f"{entry.start + middle:.3f}",
                                   "-i", str(video), "-frames:v", "1", "-y", str(frame)])
            if result.returncode:
                continue
            x, y, w, h = popup["box"]
            peak = peak_in(frame, (x, y, x + w, y + h))
            frame.unlink(missing_ok=True)
            if peak > 250:
                return {"ok": False,
                        "note": f"the type hit {peak:.0f}/255 - pure white is banned"}
            if peak < 190:
                return {"ok": False,
                        "note": f"the type only reached {peak:.0f}/255 - too dim to read"}
            return {"ok": True,
                    "note": f"brightest type pixel {peak:.0f}/255 in {popup['text']!r} "
                            f"(cap 250, needs 190)"}
    return {"ok": True, "note": "no popups on clips - every beat was a text screen"}


def _face_scan(ffmpeg: str, video: Path, folder: Path) -> dict:
    """Scan the finished render for faces - on the pixels, not on the metadata."""
    try:
        from ..picture import faces as facemod
    except Exception as exc:                      # pragma: no cover
        return {"count": -1, "note": f"the scanner could not be loaded: {exc}"}

    why = facemod.why_unavailable()
    if why and why != "ready":        # "ready" is the all-clear, not a reason
        return {"count": -1, "note": f"no face scan: {why}"}

    seconds = grading.probe_video(ffmpeg, video).get("seconds", 0.0)
    samples = 24
    found = 0
    looked = 0
    for step in range(samples):
        at = seconds * (step + 0.5) / samples
        frame = folder / f"scan_{step:02d}.png"
        result = grading._run([ffmpeg, "-hide_banner", "-v", "error", "-ss", f"{at:.3f}",
                               "-i", str(video), "-frames:v", "1", "-y", str(frame)])
        if result.returncode:
            continue
        looked += 1
        # scan_for_faces returns (count, times). It used to be read as a list,
        # so every frame counted as two "faces" and the check failed on a clean
        # render - a wrong number is worse than no number.
        count, _times = facemod.scan_for_faces(frame, seconds=0.0, samples=1)
        found += int(count)
        frame.unlink(missing_ok=True)
    return {"count": found,
            "note": f"{looked} frames of the finished render scanned, {found} face(s) found"}


def _loop_rhyme(ffmpeg: str, video: Path, folder: Path) -> dict:
    """How close the last frame is to the first - the picture's part of a loop."""
    from PIL import Image, ImageChops

    first, last = folder / "loop_a.png", folder / "loop_b.png"
    seconds = grading.probe_video(ffmpeg, video).get("seconds", 0.0)
    for at, target in ((0.1, first), (max(seconds - 0.2, 0.0), last)):
        grading._run([ffmpeg, "-hide_banner", "-v", "error", "-ss", f"{at:.3f}",
                      "-i", str(video), "-vf", "scale=270:480", "-frames:v", "1",
                      "-y", str(target)])
    try:
        with Image.open(first) as a, Image.open(last) as b:
            difference = ImageChops.difference(a.convert("L"), b.convert("L"))
        total = sum(index * count for index, count in enumerate(difference.histogram()))
        pixels = max(sum(difference.histogram()), 1)
        first.unlink(missing_ok=True)
        last.unlink(missing_ok=True)
        return {"difference": total / pixels}
    except Exception:
        return {"difference": 255.0}


def contact_sheet(ffmpeg: str, video: Path, built: list[BuiltShot],
                  out_dir: Path, render_id: str) -> Path:
    """One real frame per shot, from the finished file, laid out with its numbers."""
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:  # pragma: no cover
        raise BuildError("Pillow is not installed") from exc

    cell_w, cell_h = 300, 534
    columns = 4
    rows = max(1, (len(built) + columns - 1) // columns)
    sheet = Image.new("RGB", (cell_w * columns, cell_h * rows), (11, 11, 15))
    pen = ImageDraw.Draw(sheet)
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    for entry in built:
        at = entry.start + entry.hold / 2.0
        frame = frames_dir / f"{render_id}_build_{entry.index:02d}.jpg"
        grading._run([ffmpeg, "-hide_banner", "-v", "error", "-ss", f"{at:.3f}",
                      "-i", str(video), "-frames:v", "1", "-q:v", "3", "-y", str(frame)])
        if not frame.exists():
            continue
        column, row = entry.index % columns, entry.index // columns
        with Image.open(frame) as image:
            sheet.paste(image.convert("RGB").resize((cell_w, cell_h)), (column * cell_w, row * cell_h))
        mean, black, _ = grading.measure(frame)
        pen.text((column * cell_w + 8, row * cell_h + 8),
                 f"{entry.index} {entry.object_hi} {entry.kind}",
                 fill=(240, 236, 220))
        pen.text((column * cell_w + 8, row * cell_h + 26),
                 f"{entry.start:.1f}-{entry.end:.1f}s  light {mean:.0f}/255  black {black:.0f}%",
                 fill=(196, 196, 210))

    sheet_path = out_dir / f"{render_id}_build_sheet.jpg"
    sheet.save(sheet_path, quality=88)
    return sheet_path
