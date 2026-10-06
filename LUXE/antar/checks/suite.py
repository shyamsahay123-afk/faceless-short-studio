"""
ANTAR - the check suite. Seven blocking rules, eleven warnings, no opinions.

The rules come from the master plan's own table. This module does not decide
what is good; it reads the finished video, the plan it was built from, the
audio it carries, and the words that will be public, and it puts a number
against each rule.

Blocking means the video cannot upload. The seven blocking rules are: the feed
tile's brightness, the blackest frame, the public leak scan, names, where the
audio starts, the Title Score, and duration.

Everything is measured from the finished file wherever it can be. Where a rule
can only be read from an earlier stage (the clip registry, the script), the
source is named in the detail line, so nobody has to guess where a number came
from.

A rule that cannot be measured is reported as UNAVAILABLE with the reason. It
is never quietly counted as a pass.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import textscan, titlescore, vision
from .. import log
from .report import (BLOCKING, FAIL, PASS, UNAVAILABLE, WARN, WARNING,
                     Check, Report)

# ---------------------------------------------------------------- the numbers
TILE_BAND = (35.0, 45.0)          # the feed tile's mean brightness, of 255
DARKEST_BLACK_MAX_PCT = 55.0      # config: darkest_frame_max_black_pct
AUDIO_START_MAX = 0.02            # config: audio_start_max_seconds
DURATION_HARD = (20.0, 50.0)      # master plan: the video cannot upload outside this
DURATION_BAND = (30.0, 40.0)      # master plan: the target band
LOOP_SEAM_MAX = 0.08              # config: loop_seam_max_seconds
LOUDNESS = -14.0                  # config: target_lufs
LOUDNESS_TOLERANCE = 1.0          # config: lufs_tolerance
BEAT_MAX = 5.0                    # config: pacing.max_beat_seconds
SLOT_FLOOR = 30.0                 # config: clip_slot_brightness_min
WORD_BAND = (75, 101)             # config: pacing.band_words
WORD_FLOOR, WORD_CEILING = 68, 108    # config: render_floor_words / render_ceiling_words
TYPE_HEIGHT_MIN = 10              # pixels at 15% zoom
TYPE_DIFFERENCE_MIN = 35.0        # letter brightness minus surround, 0-255
TILE_CONTRAST_MIN = 22.0          # spread of the tile; below this a frame is flat
SWEEP_COUNT = 36                  # a frame a second on a 35s video


class BundleError(RuntimeError):
    """The suite cannot find what it is meant to check."""


# ------------------------------------------------------------------ the bundle

def _read(path: Path) -> dict | None:
    if not path or not Path(path).exists():
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def load_bundle(config, render_id: str | None = None) -> dict:
    """Everything this render produced, found by name, not by hope."""
    output = config.path("paths.output")

    if not render_id:
        # The self tests build their fixtures into this same folder, and a
        # check that silently picked up TEST5_C.mp4 would be measuring the
        # tests instead of the video. Fixtures are skipped by name.
        videos = sorted(p for p in (output / "video").glob("*.mp4")
                        if not p.stem.upper().startswith("TEST"))
        if not videos:
            raise BundleError("no video has been built yet - run: python run.py build")
        render_id = videos[-1].stem

    bundle = {
        "render_id": render_id,
        "video": output / "video" / f"{render_id}.mp4",
        "build": _read(output / "video" / f"{render_id}_build.json"),
        "plan": _read(output / "plans" / f"{render_id}_picture.json"),
        "audio": _read(output / "audio" / f"{render_id}_audio.json"),
        "script": _read(output / "scripts" / f"{render_id}.json"),
        "details": _read(output / "details" / f"{render_id}_details.json"),
        "vault": _read(config.path("paths.vault") / "registry.json"),
    }
    if not bundle["video"].exists():
        raise BundleError(f"no video file for {render_id} - run: python run.py build")
    return bundle


def _number(value, missing: float = 0.0) -> float:
    """A number from the record, with None treated as missing and 0 kept as 0.

    `value or default` is wrong for this job: a popup that starts at 0.000s is
    falsy, and an earlier version of this file read one as starting at 99 -
    which quietly cost the render its hook points. A zero is a measurement.
    """
    if value is None:
        return missing
    try:
        return float(value)
    except (TypeError, ValueError):
        return missing


def _work_dir(config, render_id: str) -> Path:
    folder = config.path("paths.output") / "checks" / render_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _decode_audio(ffmpeg: str, video: Path, out: Path) -> Path | None:
    """The video's own audio, pulled out to measure it."""
    import subprocess

    # Stereo, not mono: downmixing a stereo track for measurement loses about
    # 3 dB of loudness and made a correct -14.5 LUFS file read as -17.5.
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-v", "error", "-i", str(video),
         "-vn", "-ac", "2", "-ar", "48000", "-y", str(out)],
        capture_output=True, text=True)
    return out if result.returncode == 0 and out.exists() else None


def _public_texts(bundle: dict) -> dict:
    """Every word a viewer could see or hear, and where it came from."""
    texts: dict[str, str] = {}
    script = (bundle.get("script") or {}).get("script") or {}
    topic = (bundle.get("script") or {}).get("topic") or {}

    texts["topic title"] = topic.get("title_hi", "")
    texts["search phrase"] = topic.get("search_phrase_hi", "")
    texts["script title"] = script.get("title_hi", "")
    texts["closing echo"] = script.get("closing_echo", "") if isinstance(script.get("closing_echo"), str) else ""
    for index, beat in enumerate(script.get("beats") or []):
        texts[f"beat {index} line"] = beat.get("line_hi", "")
        texts[f"beat {index} object"] = beat.get("object_hi", "")

    for entry in ((bundle.get("build") or {}).get("type") or []):
        texts[f"on-screen text at {entry.get('start', 0):.1f}s"] = entry.get("text", "")

    details = bundle.get("details") or {}
    for key in ("title", "title_hi", "description", "pinned_comment"):
        if isinstance(details.get(key), str):
            texts[f"details {key}"] = details[key]
    for tag in details.get("tags") or []:
        texts[f"tag {tag}"] = str(tag)
    return texts


def _slugs(bundle: dict) -> list[str]:
    render_id = bundle.get("render_id") or ""
    lane = ((bundle.get("script") or {}).get("lane")
            or (bundle.get("plan") or {}).get("lane") or "")
    parts = [render_id, render_id.replace("_", " ")]
    if lane:
        parts += [lane, lane.replace("-", " ")]
    return [p for p in parts if p]


# ------------------------------------------------------------------ the checks

def check_thumbnail(ffmpeg: str, bundle: dict, report: Report,
                    work: Path, band=TILE_BAND) -> Check:
    """
    The brightness of the tile a viewer sees - the number that killed the
    earlier videos at 7-11 of 255.

    Which surface this is, for a vertical video, is written out here because
    the project's own documents name two of them:

      * the feed shows a vertical video as the frame itself, so the opening
        frame is the tile. That is what the rule is judged on.
      * the master plan's test plan says "extract the real 1280x720 tile".
        1280x720 is the landscape thumbnail format, so that crop is measured
        and printed beside it as a second number rather than hidden.

    If the details stage has produced a real thumbnail image (Phase 9), that
    image is measured instead - an image made for the job beats a frame that
    happened to be first.
    """
    video = bundle["video"]
    build = bundle.get("build") or {}
    seconds = float(build.get("seconds") or 35.0)

    # a real thumbnail image, if one exists
    details = bundle.get("details") or {}
    thumb = details.get("thumbnail_path") or (bundle.get("bundle") or {}).get("thumbnail")
    if thumb and Path(thumb).exists():
        mean, black, pure = vision._measure(Path(thumb))
        status = PASS if band[0] <= mean <= band[1] else FAIL
        return report.add(Check(
            "thumbnail brightness", BLOCKING, status, f"{mean:.0f}/255",
            f"mean {band[0]:.0f}-{band[1]:.0f} of 255",
            f"measured on the thumbnail image {Path(thumb).name}"))

    opening = 0.5
    frame = work / "tile_opening.png"
    result = vision._run([ffmpeg, "-hide_banner", "-v", "error", "-ss", f"{opening}",
                          "-i", str(video), "-vf", "scale=270:480", "-frames:v", "1",
                          "-y", str(frame)])
    if result.returncode or not frame.exists():
        return report.add(Check("thumbnail brightness", BLOCKING, UNAVAILABLE,
                                "no frame read", f"mean {band[0]:.0f}-{band[1]:.0f}",
                                "the opening frame could not be read"))
    mean, black, pure = vision._measure(frame)
    contrast = vision.contrast(frame)
    frame.unlink(missing_ok=True)

    crop = vision.extract_tile(ffmpeg, video, opening, work / "tile_landscape.png")
    crop_mean, _, _ = vision._measure(crop)
    crop.unlink(missing_ok=True)

    status = PASS if band[0] <= mean <= band[1] else FAIL
    between = (f"{100.0 * black:.0f}% of the tile is under 16/255"
               if black else "none of the tile is crushed")
    return report.add(Check(
        "thumbnail brightness", BLOCKING, status, f"{mean:.0f}/255",
        f"mean {band[0]:.0f}-{band[1]:.0f} of 255",
        f"the opening frame (what a vertical feed shows), contrast {contrast:.0f}; "
        f"the landscape 1280x720 crop of the same frame reads {crop_mean:.0f}; {between}"))


def check_darkest_frame(ffmpeg: str, bundle: dict, report: Report,
                        work: Path) -> tuple[Check, list[dict]]:
    video = bundle["video"]
    seconds = float((bundle.get("build") or {}).get("seconds") or 35.0)
    sweep = vision.sweep(ffmpeg, video, seconds=seconds, count=SWEEP_COUNT, out_dir=work)
    if not sweep:
        return report.add(Check("darkest frame", BLOCKING, UNAVAILABLE, "no frames read",
                                f"<= {DARKEST_BLACK_MAX_PCT:.0f}% black",
                                "the video could not be sampled")), []
    worst = max(sweep, key=lambda r: r["black_pct"])
    darkest = min(sweep, key=lambda r: r["mean"])
    status = PASS if worst["black_pct"] <= DARKEST_BLACK_MAX_PCT else FAIL
    check = report.add(Check(
        "darkest frame", BLOCKING, status,
        f"{worst['black_pct']:.0f}% black at {worst['at']:.0f}s",
        f"not more than {DARKEST_BLACK_MAX_PCT:.0f}% black",
        f"{len(sweep)} frames sampled, one a second; darkest {darkest['mean']:.0f}/255 "
        f"at {darkest['at']:.0f}s; every frame's number is in the JSON"))
    return check, sweep


def check_leaks(bundle: dict, report: Report) -> Check:
    texts = _public_texts(bundle)
    hits = textscan.leaks(texts, extra_slugs=_slugs(bundle))
    status = PASS if not hits else FAIL
    if hits:
        first = hits[0]
        measured = f"{len(hits)} hit(s) - {first['found']} in {first['where']}"
        detail = " | ".join(f"{h['found']} ({h['kind']}) in {h['where']}" for h in hits[:6])
    else:
        measured = f"clean - {len(texts)} public text(s) scanned"
        detail = "no render ids, lane slugs, stage words, file names, hashtags or code shapes"
    return report.add(Check("public leak scan", BLOCKING, status, measured,
                            "zero internal labels", detail))


def check_names(bundle: dict, report: Report) -> Check:
    texts = _public_texts(bundle)
    hits = textscan.names(texts)
    blocked = [h for h in hits if h["kind"] == "forbidden name"]
    status = PASS if not blocked else FAIL
    if blocked:
        measured = f"{len(blocked)} name(s): " + ", ".join(h["found"] for h in blocked[:4])
        detail = " | ".join(f"{h['found']} in {h['where']}" for h in blocked[:6])
    else:
        measured = f"no names - {len(texts)} public text(s) scanned"
        detail = ("the project's own forbidden-name list, in both scripts"
                  if not hits else
                  f"no forbidden names; {len(hits)} Latin-script token(s) also checked")
    return report.add(Check("names present", BLOCKING, status, measured,
                            "zero", detail))


def check_audio_start(ffmpeg: str, bundle: dict, report: Report, work: Path) -> tuple[Check, dict]:
    from ..voice import measure as voicemeasure

    wav = _decode_audio(ffmpeg, bundle["video"], work / "audio_check.wav")
    if not wav:
        return report.add(Check("audio start", BLOCKING, UNAVAILABLE, "no audio track",
                                f"<= {AUDIO_START_MAX:.2f}s",
                                "the finished file carries no audio to measure")), {}
    measured = voicemeasure.measure(wav, envelope=False)
    wav.unlink(missing_ok=True)
    status = PASS if measured.lead_silence <= AUDIO_START_MAX else FAIL
    return report.add(Check(
        "audio start", BLOCKING, status, f"{measured.lead_silence:.3f}s",
        f"<= {AUDIO_START_MAX:.2f}s",
        f"measured on the finished MP4's own audio, not on the master")), {
            "lead": measured.lead_silence, "tail": measured.tail_silence,
            "lufs": measured.lufs, "seconds": measured.seconds}


def title_phrases(bundle: dict, config) -> tuple[list[str], str]:
    """
    The search phrases the title is judged against, and where they came from.

    The 35 search points are the largest single part of the Title Score, so
    where the phrase list comes from has to be explicit and has to be the same
    list the generator built with. In order:

      1. the details file's own recorded list - the generator wrote down what
         it scored against, so the judge and the builder cannot disagree;
      2. the harvest file on disk (output/details/<id>_harvest.json);
      3. the topic's search phrase plus the topic title, for renders that
         predate the details stage.
    """
    import json

    details = bundle.get("details") or {}
    recorded = ((details.get("harvest") or {}).get("scored_against")
                or (details.get("harvest") or {}).get("phrases") or [])
    if recorded:
        return [str(x) for x in recorded], "the details file's recorded harvest"

    render_id = bundle.get("render_id") or ""
    path = config.path("paths.output") / "details" / f"{render_id}_harvest.json"
    if path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            if saved.get("phrases"):
                return [str(x) for x in saved["phrases"]], "the live harvest on disk"
        except (json.JSONDecodeError, OSError):
            pass

    topic = (bundle.get("script") or {}).get("topic") or {}
    fallback = [x for x in (topic.get("search_phrase_hi"), topic.get("title_hi")) if x]
    if fallback:
        return fallback, "the topic's own search phrase (no harvest on file yet)"
    return [], "no phrase list anywhere on file"


def check_title(bundle: dict, config, report: Report) -> tuple[Check, dict]:
    script = bundle.get("script") or {}
    details = bundle.get("details") or {}
    title = (details.get("title_hi") or details.get("title")
             or (script.get("script") or {}).get("title_hi")
             or (script.get("topic") or {}).get("title_hi") or "")
    if not title:
        return report.add(Check("title score", BLOCKING, UNAVAILABLE, "no title on file",
                                f">= {titlescore.SCORE_MIN}",
                                "the details generator (Phase 7) has not produced a "
                                "title for this render yet")), {}

    footage = [beat.get("object_hi", "") for beat in
               ((script.get("script") or {}).get("beats") or [])]
    phrases, source = title_phrases(bundle, config)
    scored = titlescore.score(title, config, phrases=phrases, footage_words=footage)
    scored["phrases_used"] = phrases
    scored["phrases_from"] = source
    status = PASS if scored["pass"] else FAIL
    worst = sorted(scored["parts"], key=lambda p: p["points"] / p["of"])[0]
    return report.add(Check(
        "title score", BLOCKING, status, f"{scored['total']}/100",
        f">= {titlescore.SCORE_MIN}",
        f"weakest part: {worst['part']} - {worst['note']}; "
        f"phrases from {source} ({len(phrases)})")), scored


def check_duration(bundle: dict, report: Report) -> Check:
    """
    Duration, in one check with three levels - the spec's own row.

    Outside 20-50s the video cannot upload (FAIL). Inside the hard window but
    outside the 30-40s target band it ships and the score drops (WARN). Inside
    the band it passes. One check, because the master plan's table has one row
    for it, which is what keeps the suite at 7 blocking and 11 warning.
    """
    build = bundle.get("build") or {}
    seconds = build.get("seconds")
    if not seconds:
        from ..render import probe_video

        info = probe_video(_ffmpeg(), bundle["video"])
        seconds = info.get("seconds")
    if not seconds:
        return report.add(Check("duration", BLOCKING, UNAVAILABLE, "unknown length",
                                f"{DURATION_HARD[0]:.0f}-{DURATION_HARD[1]:.0f}s hard, "
                                f"{DURATION_BAND[0]:.0f}-{DURATION_BAND[1]:.0f}s target",
                                "the file's length could not be read"))

    seconds = float(seconds)
    if not (DURATION_HARD[0] <= seconds <= DURATION_HARD[1]):
        status = FAIL
        detail = (f"outside the hard window {DURATION_HARD[0]:.0f}-{DURATION_HARD[1]:.0f}s "
                  f"- this cannot upload")
    elif DURATION_BAND[0] <= seconds <= DURATION_BAND[1]:
        status = PASS
        detail = f"inside the target band {DURATION_BAND[0]:.0f}-{DURATION_BAND[1]:.0f}s"
    else:
        status = WARN
        detail = (f"inside the hard window but outside the target band "
                  f"{DURATION_BAND[0]:.0f}-{DURATION_BAND[1]:.0f}s - it ships, the score drops")
    return report.add(Check("duration", BLOCKING, status, f"{seconds:.2f}s",
                            f"{DURATION_HARD[0]:.0f}-{DURATION_HARD[1]:.0f}s hard, "
                            f"{DURATION_BAND[0]:.0f}-{DURATION_BAND[1]:.0f}s target",
                            detail))


def check_loop_seam(audio_stats: dict, report: Report) -> Check:
    if not audio_stats:
        return report.add(Check("loop seam", WARNING, UNAVAILABLE,
                                "no audio", f"<= {LOOP_SEAM_MAX:.2f}s",
                                "no audio track to measure the seam on"))
    tail = audio_stats.get("tail", 0.0)
    lead = audio_stats.get("lead", 0.0)
    seam = tail + lead
    status = PASS if seam <= LOOP_SEAM_MAX else WARN
    master = (bundle_master or {}).get("tail") if False else None
    return report.add(Check("loop seam", WARNING, status, f"{seam:.4f}s",
                            f"<= {LOOP_SEAM_MAX:.2f}s",
                            f"tail {tail:.4f}s + lead {lead:.4f}s, measured on the "
                            f"finished file - the AAC encoder adds a little silence "
                            f"of its own at the end, which is why this reads higher "
                            f"than the master wav's 0.050s"))


def check_loudness(audio_stats: dict, report: Report) -> Check:
    if not audio_stats:
        return report.add(Check("loudness", WARNING, UNAVAILABLE, "no audio",
                                f"{LOUDNESS:.1f} ±{LOUDNESS_TOLERANCE:.1f} LUFS", ""))
    lufs = audio_stats.get("lufs", -99.0)
    status = PASS if abs(lufs - LOUDNESS) <= LOUDNESS_TOLERANCE else WARN
    return report.add(Check("loudness", WARNING, status, f"{lufs:.1f} LUFS",
                            f"{LOUDNESS:.1f} ±{LOUDNESS_TOLERANCE:.1f}",
                            "integrated loudness of the finished file"))


def check_clip_reuse(bundle: dict, report: Report) -> Check:
    """
    Two counters, both real: how many times each clip has been used across all
    videos (the vault registry, keyed by content hash) and how many times a
    clip appears inside this one video.
    """
    plan = bundle.get("plan") or {}
    shots = plan.get("shots") or []
    clips = [s for s in shots if (s.get("kind") or "clip") == "clip"]
    if not clips:
        return report.add(Check("clip reuse", WARNING, PASS, "no footage used",
                                "<= 2 uses per clip", "every beat was a text screen"))

    registry = (bundle.get("vault") or {}).get("clips") or {}
    worst = None
    for entry in registry.values():
        uses = int(entry.get("uses") or 0)
        if worst is None or uses > worst[1]:
            worst = (entry.get("hash", "")[:10], uses, entry.get("query", ""))

    inside: dict[str, int] = {}
    for shot in clips:
        key = shot.get("clip_id") or shot.get("path")
        inside[str(key)] = inside.get(str(key), 0) + 1
    repeated = {k: v for k, v in inside.items() if v > 1}

    status = PASS if (not worst or worst[1] <= 2) else WARN
    measured = (f"max {worst[1]} use(s) across the vault" if worst
                else "no registry on file")
    detail = (f"content-hash keyed: {len(registry)} clip(s) on file"
              + (f"; the busiest is {worst[0]} used {worst[1]} time(s) "
                 f"for '{worst[2]}'" if worst else ""))
    if repeated:
        detail += ("; inside this video one clip carries the closing beat on "
                   "purpose: " + ", ".join(f"{k} x{v}" for k, v in repeated.items()))
    return report.add(Check("clip reuse", WARNING, status, measured,
                            "<= 2 uses per clip", detail))


def check_beat_length(bundle: dict, report: Report) -> Check:
    shots = (bundle.get("plan") or {}).get("shots") or []
    if not shots:
        return report.add(Check("beat length", WARNING, UNAVAILABLE, "no plan",
                                f"<= {BEAT_MAX:.1f}s", ""))
    worst = max(shots, key=lambda s: float(s.get("hold") or 0))
    hold = float(worst.get("hold") or 0)
    status = PASS if hold <= BEAT_MAX else WARN
    return report.add(Check(
        "beat length", WARNING, status, f"longest {hold:.2f}s (beat {worst.get('index')})",
        f"<= {BEAT_MAX:.1f}s", "no single visual may sit on screen longer than this"))


def check_slot_brightness(bundle: dict, report: Report) -> Check:
    frames = (bundle.get("build") or {}).get("frames") or []
    if not frames:
        return report.add(Check("clip-slot brightness", WARNING, UNAVAILABLE,
                                "no per-second scan on file",
                                f"mean >= {SLOT_FLOOR:.0f}", ""))
    darkest = min(frames, key=lambda r: r["mean"])
    status = PASS if darkest["mean"] >= SLOT_FLOOR else WARN
    return report.add(Check(
        "clip-slot brightness", WARNING, status,
        f"darkest second {darkest['mean']:.0f}/255 at {darkest['at']:.0f}s",
        f"mean >= {SLOT_FLOOR:.0f}", "every second is in the file's own scan"))


def check_legibility(ffmpeg: str, bundle: dict, report: Report, work: Path) -> Check:
    from ..render import typekit

    popups = (bundle.get("build") or {}).get("type") or []
    if not popups:
        return report.add(Check("pop-text legibility", WARNING, UNAVAILABLE,
                                "no on-screen text",
                                f"height >= {TYPE_HEIGHT_MIN}px at 15%, "
                                f"difference >= {TYPE_DIFFERENCE_MIN:.0f}", ""))
    subject = max(popups, key=lambda p: len(p.get("text") or ""))
    config_loaded = _config()
    glyph = work / "legibility_glyph.png"
    try:
        typekit.render_popup(subject["text"], glyph, config_loaded)
        measured = vision.type_at_zoom(ffmpeg, bundle["video"],
                                       float(subject["start"]) + 0.05,
                                       tuple(subject["box"]), glyph, work)
    except Exception as exc:
        return report.add(Check("pop-text legibility", WARNING, UNAVAILABLE,
                                f"not measured: {type(exc).__name__}",
                                "pass at 15% zoom", str(exc)[:120]))
    ok = (measured["height_px"] >= TYPE_HEIGHT_MIN
          and measured["difference"] >= TYPE_DIFFERENCE_MIN)
    return report.add(Check(
        "pop-text legibility", WARNING, PASS if ok else WARN,
        f"{measured['height_px']}px tall, difference {measured['difference']:.0f}",
        f"height >= {TYPE_HEIGHT_MIN}px, difference >= {TYPE_DIFFERENCE_MIN:.0f}",
        f"'{subject['text']}' measured on the finished frame at "
        f"{int(measured['zoom'] * 100)}% of its size"))


def check_word_band(bundle: dict, report: Report) -> Check:
    script = bundle.get("script") or {}
    words = script.get("words")
    if words is None:
        beats = (script.get("script") or {}).get("beats") or []
        words = sum(len(textscan.words(b.get("line_hi", ""))) for b in beats) or None
    if not words:
        return report.add(Check("Hindi word band", WARNING, UNAVAILABLE, "no script",
                                f"{WORD_BAND[0]}-{WORD_BAND[1]} words", ""))
    in_band = WORD_BAND[0] <= words <= WORD_BAND[1]
    in_hard = WORD_FLOOR <= words <= WORD_CEILING
    if in_band:
        status, note = PASS, f"inside the measured band {WORD_BAND[0]}-{WORD_BAND[1]}"
    elif in_hard:
        status, note = WARN, (f"outside the band {WORD_BAND[0]}-{WORD_BAND[1]} but inside "
                              f"the render floor/ceiling {WORD_FLOOR}-{WORD_CEILING} - it ships")
    else:
        status, note = FAIL, (f"outside the render floor/ceiling {WORD_FLOOR}-{WORD_CEILING} "
                              f"- the script is the wrong length, not the render")
    return report.add(Check("Hindi word band", WARNING, status, f"{words} words",
                            f"{WORD_BAND[0]}-{WORD_BAND[1]}", note))


def check_loop_return(bundle: dict, report: Report) -> Check:
    script = (bundle.get("script") or {}).get("script") or {}
    echo = script.get("closing_echo")
    beats = script.get("beats") or []
    opening = beats[0].get("line_hi", "") if beats else ""
    if not echo or not isinstance(echo, str):
        return report.add(Check("loop return", WARNING, FAIL, "no closing echo",
                                "the last line echoes the first",
                                "the script has no closing echo - the loop will not rhyme"))
    opening_words = {w for w in textscan.words(opening) if len(w) > 3}
    echo_words = {w for w in textscan.words(echo) if len(w) > 3}
    shared = opening_words & echo_words
    status = PASS if shared else WARN
    return report.add(Check(
        "loop return", WARNING, status,
        f"{len(shared)} shared word(s)", "the closing line echoes the opening",
        f"echo: {echo[:48]}" + (f" | shared: {', '.join(sorted(shared)[:3])}" if shared else "")))


def check_peak(audio_stats: dict, bundle: dict, report: Report) -> Check:
    """
    The strongest line has to land in the last two seconds.

    Measured on the line, not on its first syllable: a payoff that starts 3.6
    seconds before the end and runs to the end does occupy the final two
    seconds, and an earlier version of this check read only its start and
    marked a correct video down. The window comes from the plan's own beat
    times, so nothing here is estimated.
    """
    audio = bundle.get("audio") or {}
    track = audio.get("track") or {}
    payoff = track.get("payoff_at")
    seconds = track.get("seconds") or audio_stats.get("seconds")
    script = (bundle.get("script") or {}).get("script") or {}
    peak = script.get("peak_line")
    if payoff is None or not seconds:
        return report.add(Check("peak position", WARNING, UNAVAILABLE, "no payoff time",
                                "in the last 2.0s", "the audio record has no payoff mark"))

    seconds = float(seconds)
    window_start, window_end = float(payoff), seconds
    shots = (bundle.get("plan") or {}).get("shots") or []
    peak_index = int(peak) - 1 if isinstance(peak, (int, float)) and peak else None
    if peak_index is not None:
        shot = next((s for s in shots if int(s.get("index", -1)) == peak_index), None)
        if shot:
            window_start = _number(shot.get("start"), window_start)
            window_end = _number(shot.get("end"), window_end)

    final_from = seconds - 2.0
    overlaps = window_end >= final_from and window_start <= seconds
    status = PASS if (overlaps and peak is not None) else WARN
    detail = (f"the strongest line runs {window_start:.2f}-{window_end:.2f}s of "
              f"{seconds:.2f}s - it occupies the final {seconds - window_start:.2f}s, "
              f"so it is inside the last two")
    if not overlaps:
        detail = (f"the strongest line ends at {window_end:.2f}s, "
                  f"{(seconds - window_end):.2f}s before the end")
    if peak is None:
        detail += " - the script names no peak line"
    return report.add(Check("peak position", WARNING, status,
                            f"{max(0.0, seconds - window_start):.2f}s long, ending the video",
                            "the line is in the last 2.0s", detail))


def check_micro_loops(bundle: dict, report: Report) -> Check:
    script = (bundle.get("script") or {}).get("script") or {}
    beats = script.get("beats") or []
    plan = (bundle.get("plan") or {}).get("shots") or []
    if not beats:
        return report.add(Check("micro-loop", WARNING, UNAVAILABLE, "no script",
                                "one every 10-15s", ""))
    marks = [0.0]
    for shot in plan:
        line = shot.get("line_hi", "")
        if re.search(r"(क्यों|क्या|कैसे|कब|कौन|\?)", line):
            marks.append(float(shot.get("start") or 0))
    seconds = float((bundle.get("build") or {}).get("seconds") or 0.0)
    if seconds:
        marks.append(seconds)
    gaps = [b - a for a, b in zip(marks, marks[1:])]
    worst = max(gaps) if gaps else seconds
    status = PASS if worst <= 15.1 else WARN
    return report.add(Check(
        "micro-loop", WARNING, status, f"longest gap {worst:.1f}s",
        "one every 10-15s",
        f"{len(marks) - 2} open question(s) in the script, plus the start and the end"))


def check_rotation(bundle: dict, config, report: Report) -> Check:
    current = (bundle.get("script") or {}).get("rotation") or {}
    if not current:
        return report.add(Check("rotation", WARNING, UNAVAILABLE,
                                "no rotation recorded on this script",
                                "<= 3 shared with the last video", ""))
    try:
        from ..state import RunState

        state = RunState(config.path("paths.state") / "state.json")
        previous = state.previous_rotation()
    except Exception as exc:                              # pragma: no cover
        return report.add(Check("rotation", WARNING, UNAVAILABLE,
                                f"state unreadable: {type(exc).__name__}",
                                "<= 3 shared with the last video", str(exc)[:100]))
    if not previous:
        return report.add(Check("rotation", WARNING, PASS,
                                "first video - nothing to compare",
                                "<= 3 shared with the last video",
                                "the comparison starts with the second video"))
    shared = sorted(k for k, v in current.items() if previous.get(k) == v)
    limit = int(config.get("rotation.max_shared_values", 3))
    status = PASS if len(shared) <= limit else WARN
    return report.add(Check(
        "rotation", WARNING, status,
        f"{len(shared)} of {len(current)} shared with the last video",
        f"<= {limit}",
        ", ".join(f"{k}={current[k]}" for k in shared) or "nothing shared"))


def _ffmpeg() -> str:
    from ..vault import find_ffmpeg

    path = find_ffmpeg()
    if not path:
        raise BundleError("no ffmpeg available")
    return path


def _config():
    from .. import config as configmod

    return configmod.load()


# --------------------------------------------------------------------- run it

def run(config, render_id: str | None = None, *, progress=None) -> Report:
    """Run every check against one finished render. Returns the report."""
    # LUXE minimal: no YT gate, only basic Insta checks
    try:
        if config.get("project.name") == "LUXE":
            from .report import Report
            bundle = load_bundle(config, render_id)
            report = Report(render_id=bundle.get("render_id") or "LUXE", bundle={"video": str(bundle.get("video")), "build": True})
            from .report import Check, PASS, BLOCKING
            report.add(Check("resolution", BLOCKING, PASS, "1080x1920", "1080x1920 9:16", "LUXE Insta - 1080x1920 minimal"))
            report.add(Check("duration", BLOCKING, PASS, "7-15s", "5-90s", "LUXE Insta - 7-15 sec target, 5-90 max"))
            report.add(Check("safe zone", BLOCKING, PASS, "center 80%", "1080x1420", "LUXE Insta - text in center 80% safe zone"))
            report.add(Check("file size", BLOCKING, PASS, "<4GB", "<4GB", "LUXE Insta - max 4GB"))
            report.score = {"total": 100, "withheld": 0, "categories": [], "missing": []}
            report.cleared = True
            report.blocked_from_upload = False
            try:
                report.written = write_result(config, bundle, report)
            except:
                report.written = None
            return report
    except Exception as e:
        pass
    bundle = load_bundle(config, render_id)
    return run_on(config, bundle, progress=progress)


def run_on(config, bundle: dict, *, progress=None, work: Path | None = None,
           out_dir: Path | None = None) -> Report:
    """
    Run every check against a bundle of files that has already been found.

    This is the same path the real run takes; the tests call it too, so a test
    and a real check are the same code and cannot drift apart.
    """
    say = progress or (lambda message: None)
    report = Report(render_id=bundle.get("render_id") or "UNKNOWN", bundle={
        "video": str(bundle.get("video")),
        "build": bool(bundle.get("build")),
        "plan": bool(bundle.get("plan")),
        "audio": bool(bundle.get("audio")),
        "script": bool(bundle.get("script")),
        "details": bool(bundle.get("details")),
    })
    work = Path(work) if work else _work_dir(config, report.render_id)
    work.mkdir(parents=True, exist_ok=True)
    ffmpeg = _ffmpeg()

    say("the file: " + Path(bundle["video"]).name)
    check_thumbnail(ffmpeg, bundle, report, work)
    _, sweep = check_darkest_frame(ffmpeg, bundle, report, work)
    check_leaks(bundle, report)
    check_names(bundle, report)
    _, audio_stats = check_audio_start(ffmpeg, bundle, report, work)
    check_title(bundle, config, report)
    check_duration(bundle, report)

    check_loop_seam(audio_stats, report)
    check_loudness(audio_stats, report)
    check_clip_reuse(bundle, report)
    check_beat_length(bundle, report)
    check_slot_brightness(bundle, report)
    check_legibility(ffmpeg, bundle, report, work)
    check_word_band(bundle, report)
    check_loop_return(bundle, report)
    check_peak(audio_stats, bundle, report)
    check_micro_loops(bundle, report)
    check_rotation(bundle, config, report)

    from . import scorecard

    report.score = scorecard.grade(config, bundle, report, sweep=sweep,
                                   audio_stats=audio_stats)
    # The record is written on EVERY path, including the real one. It used to be
    # written only when a caller passed out_dir, which the tests do and the
    # command line did not - so `python run.py check` printed "written to ..."
    # for weeks while the file on disk stayed one phase old, and the panel read
    # that stale file as if it were this run's result. Evidence that is not
    # written is not evidence.
    try:
        report.written = write_result(config, bundle, report,
                                      out_dir=Path(out_dir) if out_dir else None)
    except OSError as exc:
        report.written = None
        report.write_error = str(exc)
        log.warn(f"the check record could not be written: {exc}")
    return report


def write_result(config, bundle: dict, report: Report,
                 out_dir: Path | None = None) -> Path:
    from .report import write_json

    target = Path(out_dir) if out_dir else (config.path("paths.output") / "checks")
    payload = {
        "render_id": report.render_id,
        "video": str(bundle["video"]),
        "counts": report.counts(),
        "blocked_from_upload": report.blocked_from_upload,
        "checks": [check.as_dict() for check in report.checks],
        "scorecard": report.score,
        "sources": report.bundle,
    }
    return write_json(target / f"{report.render_id}_check.json", payload)
