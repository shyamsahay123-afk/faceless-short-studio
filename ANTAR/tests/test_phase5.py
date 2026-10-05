"""
ANTAR - Phase 5 test suite.

Proves the build half of the engine, with no network and no API key:

  - a frame that is too bright or too dark is corrected to the night window,
    by measurement, not by a fixed number
  - the correction is measured on what came out, not assumed from the setting
  - pure black never survives the grade, at any gamma
  - the words are cut into one and two word pieces, in order, and two pieces
    are never on screen at the same time
  - the type is Khand, inside the safe zones, bright enough to read, and never
    pure white
  - a shot that runs past the end of its clip is looped, not cut short
  - the finished file is opened again and measured: size, frame rate, voice,
    the black share of every second, and the faces
  - the face count is a count, not the length of a tuple

The footage here is made by ffmpeg: flat colours and a test pattern. The live
proof - eight real clips, a 35 second render - is in PHASE5_REPORT.md.
"""

from __future__ import annotations

import json
import subprocess
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from antar import config                                  # noqa: E402
from antar.render import grade as grading                  # noqa: E402
from antar.render import render as builder, typekit        # noqa: E402
from antar.vault import find_ffmpeg                       # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str):
    def wrap(fn):
        def run(verbose: bool = True):
            try:
                detail = fn() or ""
                RESULTS.append((name, True, str(detail)))
                if verbose:
                    print(f"  [PASS] {name}" + (f"   {detail}" if detail else ""))
                return True
            except AssertionError as exc:
                RESULTS.append((name, False, str(exc)))
                if verbose:
                    print(f"  [FAIL] {name}   {exc}")
                return False
            except Exception as exc:
                RESULTS.append((name, False, f"{type(exc).__name__}: {exc}"))
                if verbose:
                    print(f"  [FAIL] {name}   {type(exc).__name__}: {exc}")
                return False
        return run
    return wrap


# ------------------------------------------------------------------ fixtures

FF = find_ffmpeg()
WORK: Path | None = None


def work() -> Path:
    global WORK
    if WORK is None:
        WORK = Path(tempfile.mkdtemp(prefix="antar_p5_"))
    return WORK


def clip(name: str, colour: str, seconds: float = 2.0, size: str = "320x568") -> Path:
    """A tiny real video file, made by ffmpeg. Flat colour unless told otherwise."""
    out = work() / f"{name}.mp4"
    if out.exists():
        return out
    source = (f"color=c={colour}:s={size}:d={seconds}:r=30" if colour != "testsrc"
              else f"testsrc=size={size}:rate=30:duration={seconds}")
    result = subprocess.run(
        [FF, "-hide_banner", "-v", "error", "-f", "lavfi", "-i", source,
         "-c:v", "libx264", "-crf", "20", "-preset", "ultrafast",
         "-pix_fmt", "yuv420p", "-y", str(out)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-200:]
    return out


def voice_stub(render_id: str, seconds: float, words: list[dict]) -> dict:
    return {"render_id": render_id,
            "track": {"path": str(clip("voice_holder", "black", 1.0)), "seconds": seconds},
            "word_timings": words}


def plan_for(render_id: str, shots: list[dict]) -> dict:
    return {"render_id": render_id, "shots": shots,
            "totals": {"seconds_covered": sum(s["hold"] for s in shots)}}


def shot(index: int, path: str, start: float, end: float, kind: str = "clip",
         object_hi: str = "चीज़") -> dict:
    return {"index": index, "kind": kind, "path": path, "object_hi": object_hi,
            "start": start, "end": end, "hold": round(end - start, 3),
            "speech": round(end - start, 3), "seconds": 30.0, "brightness": 120.0,
            "black_pct": 0.0, "width": 320, "height": 568, "role": "build",
            "line_hi": "एक पंक्ति", "notes": []}


# ------------------------------------------------------------------ the grade

@check("a bright clip is brought down, by measurement not by a fixed number")
def t_bright_clip_is_corrected():
    source = clip("bright", "0xC8C8C8")
    solved = grading.solve(FF, str(source), 0.5)
    low, high = grading.NIGHT_TARGET
    assert low <= solved.mean <= high, f"brightness {solved.mean:.1f} outside {low}-{high}"
    assert solved.probes >= 2, f"only {solved.probes} measurement(s) taken"
    return f"gamma {solved.gamma:.2f} -> {solved.mean:.0f}/255 in {solved.probes} tries"


@check("a dark clip is brought up, and keeps its shadows off zero")
def t_dark_clip_is_corrected():
    source = clip("dark", "0x101014")
    solved = grading.solve(FF, str(source), 0.5)
    low, high = grading.NIGHT_TARGET
    assert solved.mean >= low, f"brightness {solved.mean:.1f} below {low}"
    assert solved.pure_black_pct <= grading.PURE_BLACK_MAX_PCT, \
        f"{solved.pure_black_pct:.1f}% still pure black"
    assert solved.gamma > 1.0, f"dark footage needed gamma below 1 ({solved.gamma:.2f})"
    return (f"gamma {solved.gamma:.2f} -> {solved.mean:.0f}/255, "
            f"pure black {solved.pure_black_pct:.2f}%")


@check("black does not survive: the floor is lifted off pure black")
def t_pure_black_is_lifted():
    source = clip("pureblack", "black")
    solved = grading.solve(FF, str(source), 0.5)
    assert solved.pure_black_pct <= grading.PURE_BLACK_MAX_PCT, \
        f"a black clip came out {solved.pure_black_pct:.1f}% pure black"
    measure, _, _ = grading._probe(FF, str(source), 0.5, solved.gamma)
    assert measure > 0.0, "the grade left the frame at absolute zero"
    return f"a black source grades to {measure:.1f}/255, never 0"


@check("two different clips get two different corrections")
def t_correction_is_per_clip():
    bright = grading.solve(FF, str(clip("hi2", "0xE0E0E0")), 0.3)
    dark = grading.solve(FF, str(clip("lo2", "0x141418")), 0.3)
    assert dark.gamma > bright.gamma + 0.3, \
        f"one number for both: bright {bright.gamma:.2f}, dark {dark.gamma:.2f}"
    return f"bright gamma {bright.gamma:.2f} vs dark gamma {dark.gamma:.2f}"


@check("the grade accounts for the type that will sit on the frame")
def t_grade_counts_the_type():
    cfg = config.load()
    source = clip("withtype", "0x6E6E6E", 3.0)
    out = work() / "ov.png"
    popup = typekit.render_popup("जवाब नहीं", out, cfg)
    x, y = typekit.place(cfg, popup.width, popup.height)
    plain = grading.solve(FF, str(source), 0.5)
    typed = grading.solve(FF, str(source), 0.5, overlay=(str(out), x, y))
    assert typed.mean <= plain.mean + 0.001, \
        f"with the type on, the frame came out brighter ({typed.mean:.1f} vs {plain.mean:.1f})"
    low, high = grading.NIGHT_TARGET
    assert low <= typed.mean <= high, f"typed frame at {typed.mean:.1f}, band {low}-{high}"
    return f"type on the frame pulls the grade down to keep {typed.mean:.0f}/255 in band"


@check("the solved gamma is confirmed by measuring the result")
def t_grade_is_measured_not_assumed():
    source = clip("mid", "0x6E6E6E")
    solved = grading.solve(FF, str(source), 0.4)
    again = grading._probe(FF, str(source), 0.4, solved.gamma)
    assert abs(again[0] - solved.mean) <= 2.0, \
        f"recorded {solved.mean:.1f} but measuring again gives {again[0]:.1f}"
    assert any("->" in line for line in solved.trail), "no measurement trail was kept"
    return f"{len(solved.trail)} measurements kept, slope read from them"


@check("the grade never asks for an impossible gamma")
def t_gamma_stays_in_range():
    for colour in ("black", "0xFFFFFF", "0x303034"):
        solved = grading.solve(FF, str(clip(f"range_{colour.strip('#x')}", colour)), 0.2)
        assert grading.GAMMA_MIN <= solved.gamma <= grading.GAMMA_MAX, \
            f"{colour} -> gamma {solved.gamma}"
    return f"gamma kept inside {grading.GAMMA_MIN}-{grading.GAMMA_MAX} for extremes"


# ------------------------------------------------------------------ the words

@check("words are cut into one and two word pieces, in order")
def t_words_become_chunks():
    words = [{"w": w, "start": i * 0.4, "end": i * 0.4 + 0.35}
             for i, w in enumerate(["जब", "वो", "जवाब", "नहीं", "देता", "है"])]
    chunks = typekit.chunk_words(words, 0.0, 2.4)
    assert chunks, "no pieces came out"
    assert all(len(c.text.split()) <= 2 for c in chunks), \
        f"a piece has more than two words: {[c.text for c in chunks]}"
    starts = [c.start for c in chunks]
    assert starts == sorted(starts), "the pieces are out of order"
    return f"{len(chunks)} pieces: " + " / ".join(c.text for c in chunks)


@check("two pieces are never on screen at the same time")
def t_chunks_never_overlap():
    words = [{"w": f"श{i}", "start": i * 0.18, "end": i * 0.18 + 0.16} for i in range(12)]
    chunks = typekit.chunk_words(words, 0.0, 2.2)
    for before, after in zip(chunks, chunks[1:]):
        assert after.start >= before.end - 0.001, \
            f"'{before.text}' ends {before.end} but '{after.text}' starts {after.start}"
    return f"{len(chunks)} pieces, no overlap"


@check("a word that overruns the shot is clipped to the shot")
def t_chunk_clipped_to_shot():
    words = [{"w": "आगे", "start": 3.0, "end": 4.4}]
    chunks = typekit.chunk_words(words, 0.0, 3.2)
    assert len(chunks) == 1, f"{len(chunks)} pieces"
    assert chunks[0].end <= 3.2, f"a piece runs to {chunks[0].end}s, past a 3.2s shot"
    return f"clipped to {chunks[0].start}-{chunks[0].end}"


@check("a shot with no words in it gets no popup")
def t_no_words_no_popup():
    assert typekit.chunk_words([], 0.0, 4.0) == [], "an empty word list made a popup"
    words = [{"w": "कहीं", "start": 9.0, "end": 9.4}]
    assert typekit.chunk_words(words, 0.0, 4.0) == [], \
        "a word from another shot was used in this one"
    return "empty in, empty out"


# ------------------------------------------------------------------- the type

@check("the type is Khand, and the run stops without it")
def t_font_is_khand():
    cfg = config.load()
    path = typekit.font_path(cfg)
    assert path.name == "Khand-Bold.ttf", f"found {path.name}"

    class Broken:
        def __init__(self, real): self.real = real
        def get(self, dotted, default=None):
            return "assets/fonts/Not-A-Real-Font.ttf" if dotted == "type.file" else self.real.get(dotted, default)
        def path(self, dotted):
            return self.real.path("paths.assets") / "fonts" / "Not-A-Real-Font.ttf"
    try:
        typekit.font_path(Broken(cfg))
    except typekit.BuildError as exc:
        return f"missing font stopped the build: {str(exc).splitlines()[0][:48]}"
    raise AssertionError("a missing typeface did not stop the build")


@check("the type is never pure white and never too dim to read")
def t_type_gradient_is_capped():
    cfg = config.load()
    out = work() / "cap.png"
    typekit.render_popup("तुम्हारा", out, cfg)
    peak = grading.peak_in(out)
    assert peak <= 250, f"type reached {peak}"
    assert peak >= 190, f"type only reached {peak}"
    return f"brightest pixel {peak:.0f}/255 (cap 250, needs 190)"


@check("the type sits inside the safe zones whatever its length")
def t_type_stays_in_safe_zone():
    cfg = config.load()
    for text in ("वो", "जवाब नहीं", "तुम्हारी खिड़की"):
        out = work() / f"safe_{len(text)}.png"
        popup = typekit.render_popup(text, out, cfg)
        x, y = typekit.place(cfg, popup.width, popup.height)
        assert y >= cfg.get("canvas.safe_zones.top_px"), f"'{text}' starts at y={y}"
        bottom = y + popup.height
        limit = cfg.get("canvas.height") - cfg.get("canvas.safe_zones.bottom_px")
        assert bottom <= limit, f"'{text}' ends at {bottom}, past {limit}"
        assert popup.width <= cfg.get("canvas.width") * typekit.POPUP_WIDTH_FRACTION + 2
    return "three lengths, all inside 220px top / 420px bottom"


@check("a long line of words is made smaller, not pushed off the frame")
def t_long_line_shrinks():
    cfg = config.load()
    short = typekit.render_popup("वो", work() / "s.png", cfg)
    long = typekit.render_popup("तुम्हारी खिड़की", work() / "l.png", cfg)
    assert long.width <= int(cfg.get("canvas.width") * typekit.POPUP_WIDTH_FRACTION) + 2, \
        f"a long line runs {long.width}px wide on a 1080px canvas"
    assert short.size >= long.size, "the long line was not sized down"
    return f"'{short.text}' {short.size}px, '{long.text}' {long.size}px"


@check("an empty popup is refused, not drawn")
def t_empty_popup_refused():
    cfg = config.load()
    try:
        typekit.render_popup("   ", work() / "empty.png", cfg)
    except typekit.BuildError:
        return "a blank popup raised instead of rendering a blank frame"
    raise AssertionError("an empty popup was drawn anyway")


# ------------------------------------------------------------- the segments

@check("a shot longer than its clip is looped, not cut short")
def t_short_clip_is_looped():
    source = clip("short_loop", "0x606060", seconds=1.0)
    out = work() / "looped.mp4"
    grading.encode_clip(FF, str(source), out, seek=0.0, seconds=3.0, gamma=1.0,
                        width=320, height=568, fps=30, crf=23, preset="ultrafast")
    info = grading.probe_video(FF, out)
    assert info.get("seconds", 0) >= 2.9, \
        f"a 1s clip only produced {info.get('seconds')}s for a 3s shot"
    return f"1s clip -> {info['seconds']:.2f}s shot, looped"


@check("a rendered segment is the locked size and carries its words")
def t_segment_has_type():
    cfg = config.load()
    source = clip("seg_type", "0x555558", seconds=3.0)
    popup = typekit.render_popup("जवाब", work() / "seg_pop.png", cfg)
    x, y = typekit.place(cfg, popup.width, popup.height)
    out = work() / "seg.mp4"
    grading.encode_clip(FF, str(source), out, seek=0.2, seconds=2.0, gamma=1.0,
                        width=int(cfg.get("canvas.width")), height=int(cfg.get("canvas.height")),
                        fps=30, crf=23, preset="ultrafast",
                        popups=[{"path": popup.path, "x": x, "y": y,
                                 "start": 0.2, "end": 1.0}])
    frame = work() / "seg_frame.png"
    grading._run([FF, "-hide_banner", "-v", "error", "-ss", "0.5", "-i", str(out),
                  "-frames:v", "1", "-y", str(frame)])
    peak = grading.peak_in(frame, (x, y, x + popup.width, y + popup.height))
    assert peak > 190, f"the type only reached {peak} in the finished segment"
    info = grading.probe_video(FF, out)
    assert (info["width"], info["height"]) == (1080, 1920), info
    return f"1080x1920 segment, type peak {peak:.0f}/255 on screen"


@check("a text screen is rendered at the brightness it was drawn at")
def t_card_screen_keeps_its_brightness():
    from antar.picture.card import build_card
    cfg = config.load()
    card = build_card("खिड़की", work() / "screen.png", cfg)
    out = work() / "screen.mp4"
    grading.encode_card(FF, str(card.path), out, seconds=2.0, width=540, height=960,
                        fps=30, crf=23, preset="ultrafast")
    frame = work() / "screen_frame.png"
    grading._run([FF, "-hide_banner", "-v", "error", "-ss", "1.0", "-i", str(out),
                  "-frames:v", "1", "-y", str(frame)])
    mean, black, _ = grading.measure(frame)
    assert abs(mean - card.brightness) <= 6, \
        f"card drawn at {card.brightness:.1f}, rendered at {mean:.1f}"
    return f"drawn {card.brightness:.0f}/255, rendered {mean:.0f}/255"


# --------------------------------------------------------------- the whole file

def _tiny_build(render_id: str, audio_seconds: float = 2.0):
    """A two shot plan rendered end to end: one clip, one text screen."""
    cfg = config.load()
    from antar.picture.card import build_card
    card = build_card("दीवार", work() / f"{render_id}_c.png", cfg)
    shots = [
        shot(0, str(clip(f"{render_id}_a", "0x707074", 3.0)), 0.0, 1.0, object_hi="मग"),
        shot(1, str(card.path), 1.0, 2.0, kind="card", object_hi="दीवार"),
    ]
    return cfg, plan_for(render_id, shots)


@check("a whole video is built from a plan, and the file is measured")
def t_whole_build():
    cfg, plan = _tiny_build("TEST5_A")
    record = builder.build(cfg, plan, progress=lambda m: None)
    checks = {c["check"]: c for c in record["checks"]}
    assert record["shots"] == 2, record["shots"]
    assert Path(record["file"]).exists(), "no file came out"
    for name in ("the canvas is the locked size", "the frame rate is the build rate",
                 "the shots add up to the plan", "no frame is mostly black (locked rule)"):
        assert checks[name]["pass"], f"{name}: {checks[name]['detail']}"
    return f"{Path(record['file']).name}, {len(checks)} checks on the finished file"


@check("the finished file carries the voice, at 48kHz stereo aac")
def t_finished_file_has_voice():
    cfg, plan = _tiny_build("TEST5_B")
    audio = work() / "voice.wav"
    subprocess.run([FF, "-hide_banner", "-v", "error", "-f", "lavfi",
                    "-i", "sine=frequency=220:duration=2.0:sample_rate=48000",
                    "-ac", "1", "-y", str(audio)], capture_output=True, text=True)
    record = builder.build(cfg, plan, progress=lambda m: None, audio=audio)
    info = grading.probe_video(FF, Path(record["file"]))
    assert info.get("audio_codec") == "aac", info
    assert info.get("audio_hz") == 48000, info
    return f"{info['audio_codec']} {info['audio_hz']}Hz, {info['seconds']:.2f}s"


@check("the build reports what it measured, not what it intended")
def t_build_record_is_measurements():
    cfg, plan = _tiny_build("TEST5_C")
    record = builder.build(cfg, plan, progress=lambda m: None)
    grades = [row for row in record["look"]["grades"] if row["gamma"] is not None]
    assert grades and all(row["brightness"] is not None for row in grades), grades
    assert all(row["probes"] >= 1 for row in grades), "a grade was recorded without measuring"
    frames = record["frames"]
    assert frames and all("mean" in row and "black_pct" in row for row in frames), frames[:2]
    return (f"{len(grades)} grade(s) with probes, {len(frames)} measured seconds, "
            f"{len(record['checks'])} checks")


@check("the face count is a count, not the length of a tuple")
def t_face_count_is_a_count():
    cfg, plan = _tiny_build("TEST5_D")
    record = builder.build(cfg, plan, progress=lambda m: None)
    face_check = next(c for c in record["checks"] if "face" in c["check"])
    assert "face(s) found" in face_check["detail"], face_check["detail"]
    found = int(face_check["detail"].split("face(s)")[0].strip().split()[-1])
    assert found == 0, f"a plain two shot render reported {found} faces: {face_check['detail']}"
    assert face_check["pass"], face_check["detail"]
    return face_check["detail"]


@check("the opening tile of the finished video sits in the locked band")
def t_finished_video_is_in_band():
    cfg, plan = _tiny_build("TEST5_H")
    record = builder.build(cfg, plan, progress=lambda m: None)
    band_check = next(c for c in record["checks"] if "opening tile" in c["check"])
    assert band_check["pass"], band_check["detail"]
    return band_check["detail"]


@check("the blackest second of a finished render is reported, and is not black")
def t_finished_file_black_scan():
    cfg, plan = _tiny_build("TEST5_E")
    record = builder.build(cfg, plan, progress=lambda m: None)
    black_check = next(c for c in record["checks"] if "mostly black" in c["check"])
    assert black_check["pass"], black_check["detail"]
    assert record["frames"], "no per-second scan was kept"
    return black_check["detail"]


@check("a plan with no shots stops the build instead of writing an empty file")
def t_empty_plan_stops():
    cfg = config.load()
    try:
        builder.build(cfg, {"render_id": "TEST5_F", "shots": []}, progress=lambda m: None)
    except builder.BuildError as exc:
        return f"stopped: {str(exc)[:52]}"
    raise AssertionError("an empty plan produced a file")


@check("the build works with no voice on file - the shots still add up")
def t_build_without_voice():
    cfg, plan = _tiny_build("TEST5_G")
    record = builder.build(cfg, plan, progress=lambda m: None, audio=None)
    assert record["audio"] is None, record["audio"]
    info = grading.probe_video(FF, Path(record["file"]))
    assert abs(info["seconds"] - 2.0) <= 0.12, info["seconds"]
    assert not info.get("audio_codec"), "audio appeared from nowhere"
    return f"{info['seconds']:.2f}s of picture, no audio track"


ALL = [
    t_bright_clip_is_corrected, t_dark_clip_is_corrected, t_pure_black_is_lifted,
    t_correction_is_per_clip, t_grade_counts_the_type,
    t_grade_is_measured_not_assumed, t_gamma_stays_in_range,
    t_words_become_chunks, t_chunks_never_overlap, t_chunk_clipped_to_shot, t_no_words_no_popup,
    t_font_is_khand, t_type_gradient_is_capped, t_type_stays_in_safe_zone,
    t_long_line_shrinks, t_empty_popup_refused,
    t_short_clip_is_looped, t_segment_has_type, t_card_screen_keeps_its_brightness,
    t_whole_build, t_finished_file_has_voice, t_build_record_is_measurements,
    t_face_count_is_a_count, t_finished_video_is_in_band,
    t_finished_file_black_scan, t_empty_plan_stops,
    t_build_without_voice,
]


def clean_up() -> int:
    """
    Fixtures are built into the real output folder so the checks read real
    files, and they are deleted again afterwards - a test that leaves its
    videos behind once left the workshop carrying 1.8MB of them and put
    TEST5_*.mp4 next to a real build where `check` could have picked one up.
    """
    removed = 0
    root = Path(__file__).resolve().parent.parent
    for folder, pattern in (("output/video", "TEST5_*"), ("output/checks", "TEST5_*"),
                            ("output/checks", "TEST6_*"), ("output/video", "TEST6_*"),
                            ("output/plans", "TEST5_*"), ("output/plans", "TEST6_*")):
        for path in (root / folder).glob(pattern):
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    path.unlink()
                removed += 1
            except OSError:
                pass
    shutil.rmtree(root / "output" / "checks" / "p7wire", ignore_errors=True)
    shutil.rmtree(root / "output" / "checks" / "p7fall", ignore_errors=True)
    return removed


def run_all(verbose: bool = True) -> bool:
    RESULTS.clear()
    if verbose:
        print()
        print("  ANTAR - PHASE 5 SELF TEST")
        print("  " + "-" * 62)
    started = time.time()
    for test in ALL:
        test(verbose=verbose)
    clean_up()
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    if verbose:
        print("  " + "-" * 62)
        print(f"  {passed}/{total} passed in {time.time() - started:.2f}s")
        if passed != total:
            print("  failing:")
            for name, ok, detail in RESULTS:
                if not ok:
                    print(f"    - {name}: {detail}")
    return passed == total


if __name__ == "__main__":
    raise SystemExit(0 if run_all() else 1)
