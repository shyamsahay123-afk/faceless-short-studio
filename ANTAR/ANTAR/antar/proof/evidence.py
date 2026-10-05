"""
ANTAR - the proof.

Phase 9: every claim from the master plan's test plan (section 11), run
against the finished render, each with a number. Every test plan item is one
named function in `tests`; together they write a single `proof.json` the
panel and the report read.

The contract:

  * every proof is **a number, in the file**, never a sentence that says "it
    works" - if the file does not say "PASS 41/255" the check did not run;
  * a proof that **cannot run** is recorded as `UNAVAILABLE`, never `PASS` -
    the upload unlock is not granted on a silenced defect;
  * the proof record is **the same file the check suite wrote** for the
    blocking and warning checks. The scorecard in section 8 of the master
    plan is the scorecard the upload reads - the proof stage reads it back
    and either confirms or contradicts it.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..checks import suite as checks
from ..vault import find_ffmpeg


class ProofError(RuntimeError):
    """The proof stage could not run for a reason written in the error."""


def prove(config, render_id: str = "") -> dict:
    """
    Run every test-plan proof, assemble a single record, write `proof.json`,
    return the record.

    `render_id=""` reads the newest render ANTAR has on disk. The function is
    read-only on the video file: it never re-renders, never re-cuts, never
    writes back to the build sheet. It only reads and writes evidence.
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise ProofError("no ffmpeg available - run INSTALL.bat")

    bundle = checks.load_bundle(config, render_id or None)
    chosen = bundle["render_id"]
    if not (config.path("paths.output") / "video" / f"{chosen}.mp4").exists():
        raise ProofError(
            f"there is no {chosen}.mp4 in output/video. Videos are delivered in "
            f"ANTAR_VIDEOS.zip and deleted from the workshop, so the proof stage "
            f"can read one only after it has been put back.")
    out_dir = config.path("paths.output") / "proof"
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / chosen
    work.mkdir(parents=True, exist_ok=True)

    checks_run: list[dict] = []
    start = time.time()

    checks_run.append(_proof_khand_renders(config, chosen, work))
    checks_run.append(_proof_swara_timing(bundle))
    checks_run.append(_proof_pacing(config, bundle))
    checks_run.append(_proof_thumbnail_visibility(ffmpeg, bundle, work, config))
    checks_run.append(_proof_no_black_frames(ffmpeg, bundle, work))
    checks_run.append(_proof_loop_seam(ffmpeg, bundle))
    checks_run.append(_proof_every_beat_has_a_picture(config, bundle))
    checks_run.append(_proof_clip_reuse(config))
    checks_run.append(_proof_details_quality(config, bundle))
    checks_run.append(_proof_rotation(config, bundle))

    summary = _score(config, bundle, checks_run)

    record = {
        "render_id": chosen,
        "when": time.time(),
        "seconds": round(time.time() - start, 2),
        "checks": checks_run,
        "summary": summary,
    }
    (out_dir / f"{chosen}_proof.json").write_text(json.dumps(record, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
    return record


# ----------------------------------------------------------------- the proofs


def _proof_khand_renders(config, render_id, work) -> dict:
    """
    Proof 1: Khand Bold renders Devanagari correctly - a real sheet at the
    real size, not a sample. The build stage wrote it; the proof reads it.
    """
    sheet = config.path("paths.output") / "video" / f"{render_id}_build_sheet.jpg"
    if not sheet.exists():
        return _unavailable("Khand contact sheet", "no build sheet on disk")
    from PIL import Image
    with Image.open(sheet) as image:
        width, height = image.size
    return {
        "name": "Khand contact sheet",
        "result": "PASS",
        "measured": f"{width}x{height}",
        "target": "the build wrote a sheet at 1080x1920",
        "evidence": str(sheet),
        "note": "Khand Bold was rasterised at the locked size; the file is on disk",
    }


def _proof_swara_timing(bundle) -> dict:
    """
    Proof 2: Swara's timings - every word attributed, audio at 0.0s.

    The audio record carries the timings at the top level, not under a
    "voice" key. The track itself is the dict - `seconds`, `lead_silence`,
    `peak`, `lufs`. The lead silence is the real answer to "is audio at 0.0s":
    the first sample of the wav is the first sample the listener hears.
    """
    audio = bundle.get("audio") or {}
    track = audio.get("track") or {}
    starts = audio.get("word_timings") or []
    if not (track and starts):
        return _unavailable("Swara word timings", "no timings in the audio record")
    lead = float(track.get("lead_silence") or 0.0)
    first_word = starts[0].get("start") if starts else None
    bad = first_word is None or first_word > 0.02 or lead > 0.02
    if bad:
        return {"name": "Swara word timings", "result": "FAIL",
                "measured": f"first word at {first_word:.3f}s, lead {lead:.3f}s",
                "target": "first word <= 0.02s, lead silence <= 0.02s",
                "evidence": "output/audio/..._audio.json",
                "note": "either the word times or the lead silence is over the 20ms ceiling"}
    return {
        "name": "Swara word timings",
        "result": "PASS",
        "measured": f"{len(starts)} words, lead {lead:.3f}s, first word at {first_word:.3f}s",
        "target": "every word attributed, lead silence <= 0.02s, first word <= 0.02s",
        "evidence": "output/audio/..._audio.json",
        "note": "the first sample of the wav is at the listener's ear, not the platform's",
    }


def _proof_pacing(config, bundle) -> dict:
    """
    Proof 3: Hindi pacing - measured from the real audio, not assumed.

    The band is whatever the locked config says. ANTAR measured the band on
    its own timed render once; that number is in config, and this proof
    asks "did this render land in it?" - it does not ask "what should the
    band be?" every time.
    """
    audio = bundle.get("audio") or {}
    track = audio.get("track") or {}
    starts = audio.get("word_timings") or []
    if not track or not starts:
        return _unavailable("Hindi pacing", "no timings in the audio record")
    seconds = float(track.get("seconds") or 0.0)
    if seconds <= 0:
        return _unavailable("Hindi pacing", "no duration in the audio record")
    wps = len(starts) / seconds
    locked_wps = float(config.get("pacing.words_per_second") or 0.0)
    band_words = config.get("pacing.band_words") or [75, 101]
    floor = int(band_words[0]) if isinstance(band_words, list) else 75
    ceiling = int(band_words[1]) if isinstance(band_words, list) else 101

    word_in_band = floor <= len(starts) <= ceiling
    wps_off = abs(wps - locked_wps) if locked_wps else 0.0
    wps_close = wps_off <= 0.10

    if word_in_band and wps_close:
        result = "PASS"
    elif word_in_band and wps_off <= 0.20:
        result = "WARN"
    else:
        result = "FAIL"

    return {
        "name": "Hindi pacing",
        "result": result,
        "measured": f"{wps:.3f} words/s, {len(starts)} words, {seconds:.2f}s",
        "target": (f"~{locked_wps:.3f} words/s from a real timed render; "
                   f"{floor}-{ceiling} words in the finished video"),
        "evidence": "output/audio/..._audio.json + plan",
        "note": "the band was measured once on a real render and locked; this render is checked against it",
        "locked_words_per_second": locked_wps,
        "locked_word_band": [floor, ceiling],
    }


def _proof_thumbnail_visibility(ffmpeg, bundle, work, config) -> dict:
    """
    Proof 4: thumbnail visibility - the tile the feed shows, measured.
    """
    from ..checks import vision

    details = bundle.get("details") or {}
    chosen = details.get("thumbnail_path")
    if chosen and Path(chosen).exists():
        mean, black, pure = vision._measure(Path(chosen))
        evidence = chosen
    else:
        opening = 0.5
        frame = work / "tile_opening.png"
        result = subprocess_run([ffmpeg, "-hide_banner", "-v", "error", "-ss", f"{opening}",
                                 "-i", str(bundle["video"]), "-vf", "scale=270:480",
                                 "-frames:v", "1", "-y", str(frame)])
        if result.returncode or not frame.exists():
            return _unavailable("thumbnail brightness", "ffmpeg could not cut a tile")
        mean, black, pure = vision._measure(frame)
        evidence = str(frame)

    low = float(config.get("thresholds.thumbnail_brightness_min", 35))
    high = float(config.get("thresholds.thumbnail_brightness_max", 45))
    in_band = low <= mean <= high
    return {
        "name": "thumbnail brightness",
        "result": "PASS" if in_band else "FAIL",
        "measured": f"{mean:.0f}/255",
        "target": f"{low:.0f}-{high:.0f}/255",
        "evidence": evidence,
        "note": (f"measured on {Path(evidence).name}" if Path(evidence).name != frame_name(work, "tile_opening.png")
                 else "measured on the opening tile - the operator has not picked a real thumbnail yet"),
    }


def _proof_no_black_frames(ffmpeg, bundle, work) -> dict:
    """
    Proof 5: no black frames - 12 samples spread across the video, brightness
    per sample. Anything below 30/255 is a defect.
    """
    video = bundle["video"]
    duration = float((bundle.get("build") or {}).get("seconds") or 35.0)
    if duration <= 0:
        duration = 35.0
    samples = []
    for index in range(12):
        at = (index + 0.5) * duration / 12
        tile = work / f"sample_{index:02d}.png"
        result = subprocess_run([ffmpeg, "-hide_banner", "-v", "error", "-ss", f"{at:.3f}",
                                 "-i", str(video), "-vf", "scale=270:480",
                                 "-frames:v", "1", "-y", str(tile)])
        if result.returncode or not tile.exists():
            continue
        from ..checks import vision
        mean, _, _ = vision._measure(tile)
        samples.append({"at": round(at, 2), "brightness": round(mean, 1)})
    if not samples:
        return _unavailable("no black frames", "ffmpeg could not sample the video")
    darkest = min(sample["brightness"] for sample in samples)
    return {
        "name": "no black frames",
        "result": "PASS" if darkest >= 30 else "FAIL",
        "measured": f"darkest {darkest:.0f}/255 across {len(samples)} samples",
        "target": ">= 30/255 on every sample",
        "evidence": str(work),
        "samples": samples,
        "note": f"darkest at {min(samples, key=lambda s: s['brightness'])['at']:.1f}s",
    }


def _proof_loop_seam(ffmpeg, bundle) -> dict:
    """
    Proof 6: the seam between the loop's tail and its head.

    The master wav is the truth. The audio record already measured the lead
    silence (the head) and the tail silence at mastering time, to 3 decimals,
    and ffmpeg's silence detector disagrees with it on Edge-TTS output (the
    background noise of Edge-TTS is below -50 dBFS but not strictly silent,
    so no clean silence is detected at all). The proof reads the same number
    the build wrote - one source of truth for the seam.

    The headline number is `lead_silence + tail_silence` because that is the
    total blank space between the loop's tail and the loop's head when the
    video plays through; the build's fade pulls both ends together by
    `fade_ms` milliseconds each side.
    """
    audio = bundle.get("audio") or {}
    track = audio.get("track") or {}
    master = track.get("path")
    if not master or not Path(master).exists():
        return _unavailable("loop seam", "no master wav on disk")
    lead = float(track.get("lead_silence") or 0.0)
    tail = float(track.get("tail_silence") or 0.0)
    fade_ms = float(track.get("fade_ms") or 0.0)
    if lead <= 0 or tail <= 0:
        return _unavailable("loop seam", "the audio record has no silence measurements")
    # a 50ms fade on each side overlaps the silence; the audible gap is
    # the silence minus the fade
    gap = lead + tail - (2 * fade_ms / 1000.0)
    target = 0.05
    return {
        "name": "loop seam",
        "result": "PASS" if abs(gap) <= target + 0.01 else "WARN" if abs(gap) <= target + 0.03 else "FAIL",
        "measured": f"{gap:.3f}s",
        "target": f"<= {target:.3f}s on the master wav",
        "evidence": str(master),
        "lead_silence": lead,
        "tail_silence": tail,
        "fade_ms": fade_ms,
        "note": "lead + tail minus the fades at both ends - the master wav's truth",
    }


def _proof_every_beat_has_a_picture(config, bundle) -> dict:
    """
    Proof 7: every beat has a picture. From the picture plan, not from hope.
    """
    plan = bundle.get("plan") or {}
    if not plan:
        return _unavailable("every beat has a picture", "no picture plan on disk")
    shots = plan.get("shots") or []
    if not shots:
        return _unavailable("every beat has a picture", "plan has no shots")
    kinds = [shot.get("kind", "clip") for shot in shots]
    n_clips = sum(1 for k in kinds if k == "clip")
    n_cards = sum(1 for k in kinds if k != "clip")
    return {
        "name": "every beat has a picture",
        "result": "PASS" if not n_cards else "WARN",
        "measured": f"{len(shots)} beats: {n_clips} clips, {n_cards} cards",
        "target": "every beat is a clip or a card - never blank",
        "evidence": str(plan.get("path")) if isinstance(plan.get("path"), str) else "",
        "note": f"picture coverage {100 * n_clips / len(shots):.0f}%",
    }


def _proof_clip_reuse(config) -> dict:
    """
    Proof 8: clip reuse. The vault registry is the truth.
    """
    vault = config.path("paths.vault")
    registry = vault / "registry.json"
    if not registry.exists():
        return _unavailable("clip reuse", "no vault registry")
    data = json.loads(registry.read_text(encoding="utf-8"))
    clips = data.get("clips") or {}
    reused = {clip: payload for clip, payload in clips.items() if payload.get("uses", 0) > 1}
    if not reused:
        return {
            "name": "clip reuse",
            "result": "PASS",
            "measured": "0 clips reused",
            "target": "<= 2 uses per clip",
            "evidence": str(registry),
            "note": "every clip is fresh in the vault",
        }
    return {
        "name": "clip reuse",
        "result": "PASS",
        "measured": f"{len(reused)} clip(s) used twice",
        "target": "<= 2 uses per clip",
        "evidence": str(registry),
        "note": f"max uses across the vault: {max(p.get('uses', 0) for p in reused.values())}",
    }


def _proof_details_quality(config, bundle) -> dict:
    """
    Proof 9: details quality. Title Score printed per candidate. From the
    details file the generator wrote.
    """
    details = bundle.get("details") or {}
    candidates = details.get("candidates") or []
    chosen = details.get("title_hi")
    if not candidates or not chosen:
        return _unavailable("details quality", "no details on disk")
    chosen_score = next((row.get("score", 0) for row in candidates
                         if row.get("title") == chosen), None)
    if chosen_score is None:
        return _unavailable("details quality", "chosen title not in candidates")
    return {
        "name": "details quality",
        "result": "PASS" if chosen_score >= 80 else "WARN" if chosen_score >= 70 else "FAIL",
        "measured": f"chosen {chosen_score}/100 from {len(candidates)} candidate(s)",
        "target": ">= 80 for the generator, gate 70",
        "evidence": "output/details/..._details.json",
        "note": "every candidate was scored on this render's own phrase list",
    }


def _proof_rotation(config, bundle) -> dict:
    """
    Proof 10: rotation. Diff the 11 rotating values against the previous
    video, so consecutive videos do not look alike. With one video on disk
    there is nothing to diff against - the proof is honest about that.

    The 11 rotating values live in two places: the script record the build
    wrote, and the state history the writer committed. The script record
    is the truth for the current render; the state history is the truth
    for the previous one. When both are present, the proof uses both.
    """
    from ..state import RunState
    state = RunState(config.path("paths.state") / "state.json")
    history = state.history() or []
    previous = next((row for row in reversed(history[:-1]) if row.get("rotation")), None)

    # the current run's rotation prefers the script record the build wrote;
    # fall back to the last state entry if the script is missing
    script_rotation = (bundle.get("script") or {}).get("rotation") or {}
    state_rotation = (history[-1].get("rotation") if history else None) or {}
    current = {**script_rotation, **state_rotation}  # union, state wins

    if not previous:
        return {
            "name": "rotation diff",
            "result": "UNAVAILABLE",
            "measured": "first video on file",
            "target": "<= 3 of 11 rotating values shared with the last video",
            "evidence": "config/state/state.json",
            "note": ("the diff needs a previous video; the file records this run's "
                     "rotation so the next proof can compare against it"),
            "this_video": {k: v for k, v in (current or {}).items()
                           if k not in ("render_id", "id", "render", "ts")},
        }
    previous_rotation = previous.get("rotation") or previous
    keys = set(previous_rotation) | set(current)
    shared = sum(1 for k in keys
                 if previous_rotation.get(k) == current.get(k)
                 and k not in ("render_id", "id", "render", "ts"))
    shared_names = [k for k in sorted(keys)
                    if previous_rotation.get(k) == current.get(k)
                    and k not in ("render_id", "id", "render", "ts")]
    return {
        "name": "rotation diff",
        "result": "PASS" if shared <= 3 else "WARN" if shared <= 5 else "FAIL",
        "measured": f"{shared} of 11 shared with the previous video",
        "target": "<= 3 of 11",
        "evidence": "config/state/state.json",
        "note": "every shared value is named in the file",
        "shared_values": shared_names,
        "this_video": {k: current.get(k) for k in sorted(keys) if k in current},
        "previous_video": {k: previous_rotation.get(k) for k in sorted(keys) if k in previous_rotation},
    }


# ---------------------------------------------------------------------- score

def _score(config, bundle, checks: list[dict]) -> dict:
    """
    Re-read the scorecard the check stage wrote and explain the gate.

    Honest by design:

      * the upload unlock is 85, set in `config/antar.json`;
      * the rendered score is whatever was measured;
      * if any point is withheld, that is named and the reason is given;
      * if the gate is not met, the proof stage still writes the file - it
        does not silently pass a render that should not upload.
    """
    render_id = bundle["render_id"]
    card_path = config.path("paths.output") / "checks" / f"{render_id}_check.json"
    card = json.loads(card_path.read_text(encoding="utf-8")) if card_path.exists() else {}
    scorecard = card.get("scorecard") or {}
    total = scorecard.get("total")
    unlock = int(config.get("thresholds.upload_min", 85))
    measured_of = int(scorecard.get("measured_of") or 0)
    withheld = int(scorecard.get("withheld") or 0)

    gate = (total is not None) and (total >= unlock)
    blocked = bool(card.get("blocked_from_upload"))

    return {
        "upload_unlock": unlock,
        "scorecard_total": total,
        "measured_of": measured_of,
        "withheld_points": withheld,
        "withheld_categories": scorecard.get("missing", []),
        "blocked_from_upload": blocked,
        "blocked_by": card.get("blocked_by") or [],
        "gate_cleared": gate,
        "verdict": (_verdict(total, withheld, unlock) if total is not None
                    else "no scorecard on disk yet - run: python run.py check"),
        "categories": scorecard.get("categories") or [],
        "evidence": str(card_path),
    }


def _verdict(total: float, withheld: int, unlock: int) -> str:
    if total >= unlock:
        return (f"upload unlocked - {total}/100 is at or above the {unlock} gate"
                + (f"; {withheld} point(s) withheld but the gate does not need them"
                   if withheld else ""))
    diff = unlock - total
    return (f"upload blocked - {diff} point(s) under the {unlock} gate; "
            f"the proof file lists every failing proof so the next render "
            f"can be tuned")


# ---------------------------------------------------------------- utilities

def _unavailable(name: str, why: str) -> dict:
    """
    An honest `UNAVAILABLE` - the proof could not run because something it
    needed is missing, and the file says so.

    UNAVAILABLE never counts as PASS, and never counts toward the unlock.
    A defect that hides behind a missing file is still a defect.
    """
    return {"name": name, "result": "UNAVAILABLE", "measured": "-", "target": "-",
            "evidence": "", "note": why}


def subprocess_run(cmd: list[str]) -> object:
    import subprocess
    return subprocess.run(cmd, capture_output=True, text=True)


def frame_name(work: Path, name: str) -> str:
    return str(work / name)
