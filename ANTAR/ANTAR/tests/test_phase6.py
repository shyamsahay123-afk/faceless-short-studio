"""
ANTAR - Phase 6 test suite.

The phase's exit criterion, in the master plan's own words: **"Every blocking
check fires correctly on a deliberately bad render."**

So this suite renders bad videos on purpose and requires the checks to catch
them. A check that stays quiet on a broken render is worse than no check at
all, because it teaches the operator to trust a green light.

Proven here:
  - a black video fails the thumbnail rule AND the darkest-frame rule
  - a washed-out video fails the thumbnail rule from the other side
  - audio that starts 1s late fails the audio rule
  - a video that is 52s long fails duration - and so does a 12s one
  - "#Contrarian" in the script fails the leak scan
  - "Carlos" in the script fails the names scan
  - a bad title fails the Title Score
  - a good render passes every blocking check
  - a rule that cannot be measured says UNAVAILABLE and is not counted as a pass
  - the scorecard withholds what it cannot measure and refuses to award the
    unlock on a partial score

Nothing here is mocked: the videos are real files made by ffmpeg, the audio is
real, and the checks run through the same run_on() path a real run uses.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from antar import config                                    # noqa: E402
from antar.checks import run_on, suite, textscan, titlescore  # noqa: E402
from antar.checks.report import FAIL, PASS, UNAVAILABLE, WARN  # noqa: E402
from antar.vault import find_ffmpeg                         # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []
SKIPPED: list[tuple[str, str]] = []


class Skipped(Exception):
    """A test that cannot run because its input is not in the workshop.

    The finished render is delivered inside /home/user/ANTAR_VIDEOS.zip and
    deleted from the working folder - that is the user's rule - so the one test
    that reads it has to say it did not run rather than pass quietly.
    """
FF = find_ffmpeg()
WORK: Path | None = None


def check(name: str):
    def wrap(fn):
        def run(verbose: bool = True):
            try:
                detail = fn() or ""
                RESULTS.append((name, True, str(detail)))
                if verbose:
                    print(f"  [PASS] {name}" + (f"   {detail}" if detail else ""))
                return True
            except Skipped as exc:
                SKIPPED.append((name, str(exc)))
                if verbose:
                    print(f"  [SKIP] {name}   {exc}")
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


def work() -> Path:
    global WORK
    if WORK is None:
        WORK = Path(tempfile.mkdtemp(prefix="antar_p6_"))
    return WORK


# ------------------------------------------------------------------ fixtures

def make_video(name: str, *, colour: str = "0x28282C", seconds: float = 22.0,
               audio_start: float = 0.0, audio_level: str = "0.12",
               fps: int = 10, size: str = "180x320") -> Path:
    """A real little video with real audio. Colour 'black' makes a black one."""
    out = work() / f"{name}.mp4"
    if out.exists():
        return out

    video_source = f"color=c={colour}:s={size}:d={seconds}:r={fps}"
    audio = f"aevalsrc=0:d={audio_start}[sil];sine=frequency=240:duration={seconds}:sample_rate=48000,volume={audio_level}[tone];[sil][tone]concat=n=2:v=0:a=1[out]"
    result = subprocess.run(
        [FF, "-hide_banner", "-v", "error",
         "-f", "lavfi", "-i", video_source,
         "-f", "lavfi", "-i", audio,
         "-map", "0:v", "-map", "1:a",
         "-shortest", "-c:v", "libx264", "-crf", "28", "-preset", "ultrafast",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-ar", "48000",
         "-y", str(out)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-300:]
    return out


def base_script(render_id: str, *, title: str | None = None,
                lines: list[str] | None = None) -> dict:
    beats = lines or [
        "जब वो जवाब नहीं देता, तुम्हारा फ़ोन मेज़ पर पड़ा रहता है।",
        "तुम उसी मग को देखते रहते हो, जो कल से वैसे ही रखा है।",
        "वो फ़ोन तुम्हारी कीमत नहीं तय करता।",
    ]
    return {
        "render_id": render_id,
        "topic": {"title_hi": title or "लोग तुम्हें क्यों नज़रअंदाज़ करते हैं",
                  "search_phrase_hi": "लोग इग्नोर क्यों करते हैं"},
        "rotation": {"script_structure": "problem-mechanism", "hook_angle": "direct-question",
                     "duration": 22, "grade": "cold-blue", "type_size": 250},
        "words": 90,
        "script": {
            "title_hi": title or "लोग तुम्हें क्यों नज़रअंदाज़ करते हैं",
            "closing_echo": beats[0],
            "peak_line": len(beats),
            "beats": [{"line_hi": line, "object_hi": "फ़ोन", "role": "build"}
                      for line in beats],
        },
    }


def base_bundle(name: str, *, colour: str = "0x28282C", seconds: float = 22.0,
                audio_start: float = 0.0, script: dict | None = None,
                build_type: list | None = None, holds: list[float] | None = None,
                audio_level: str = "0.12") -> dict:
    video = make_video(name, colour=colour, seconds=seconds,
                       audio_start=audio_start, audio_level=audio_level)
    render_id = f"TEST6_{name.upper()}"
    holds = holds or ([seconds / 3] * 3)
    shots = []
    at = 0.0
    for index, hold in enumerate(holds):
        shots.append({"index": index, "kind": "clip", "path": str(video),
                      "object_hi": "फ़ोन", "query": "smartphone on table",
                      "clip_id": f"clip{index}", "start": round(at, 3),
                      "end": round(at + hold, 3), "hold": round(hold, 3),
                      "seconds": seconds, "line_hi": (script or base_script(render_id))
                      ["script"]["beats"][min(index, 2)]["line_hi"]})
        at += hold
    return {
        "render_id": render_id,
        "video": video,
        "script": script or base_script(render_id),
        "plan": {"render_id": render_id, "lane": "practical-psychology",
                 "shots": shots, "totals": {"seconds_covered": round(at, 3)}},
        "build": {"render_id": render_id, "seconds": round(at, 3),
                  "shots": len(shots),
                  "type": build_type if build_type is not None else [
                      {"beat": 0, "text": "जब वो", "size": 150,
                       "box": [363, 1156, 353, 188], "start": 0.0, "end": 0.8}],
                  "frames": [], "checks": []},
        "audio": {"render_id": render_id,
                  "track": {"path": str(video), "seconds": round(at, 3),
                            "payoff_at": round(at - 1.2, 3), "lead_silence": 0.01},
                  "word_timings": [{"w": "जब", "start": 0.02, "end": 0.3}]},
        "details": None,
        "vault": {"clips": {f"clip{i}": {"hash": f"clip{i}", "uses": 1, "query": "फ़ोन"}
                            for i in range(len(shots))}},
    }


def run_bundle(bundle: dict, name: str):
    cfg = config.load()
    folder = work() / name
    folder.mkdir(parents=True, exist_ok=True)
    return run_on(cfg, bundle, work=folder, out_dir=folder)


def find(report, name: str):
    return next((c for c in report.checks if c.name == name), None)


# ------------------------------------------------------------------- blocking

@check("a black video fails the thumbnail rule and the darkest-frame rule")
def t_black_video_is_caught():
    report = run_bundle(base_bundle("black", colour="black"), "black")
    thumb = find(report, "thumbnail brightness")
    dark = find(report, "darkest frame")
    assert thumb.status == FAIL, f"thumbnail read {thumb.measured}"
    assert dark.status == FAIL, f"darkest frame read {dark.measured}"
    assert report.blocked_from_upload, "a black video was not blocked"
    return f"thumbnail {thumb.measured}, darkest {dark.measured} -> blocked"


@check("a washed-out video fails the thumbnail rule from the other side")
def t_bright_video_is_caught():
    report = run_bundle(base_bundle("white", colour="0xE8E8E8"), "white")
    thumb = find(report, "thumbnail brightness")
    assert thumb.status == FAIL, f"a near-white video passed the tile rule ({thumb.measured})"
    return f"thumbnail {thumb.measured} -> blocked"


@check("audio that starts a second late fails the audio rule")
def t_late_audio_is_caught():
    report = run_bundle(base_bundle("late_audio", audio_start=1.0), "late_audio")
    audio = find(report, "audio start")
    assert audio.status == FAIL, f"a 1s late voice passed ({audio.measured})"
    assert report.blocked_from_upload, "late audio did not block"
    return f"audio start {audio.measured} -> blocked"


@check("a 52 second video fails duration, and so does a 12 second one")
def t_duration_limits_are_enforced():
    long_report = run_bundle(base_bundle("long", seconds=52.0), "long")
    short_report = run_bundle(base_bundle("short", seconds=12.0), "short")
    off_band = run_bundle(base_bundle("mid", seconds=25.0), "mid")
    long_check = find(long_report, "duration")
    short_check = find(short_report, "duration")
    mid_check = find(off_band, "duration")
    assert long_check.status == FAIL, f"52s passed ({long_check.measured})"
    assert short_check.status == FAIL, f"12s passed ({short_check.measured})"
    assert mid_check.status == WARN, f"25s read {mid_check.status}, expected WARN"
    return (f"52s {long_check.status}, 12s {short_check.status}, "
            f"25s {mid_check.status} (ships, score drops)")


@check("#Contrarian in the script fails the leak scan")
def t_internal_label_is_caught():
    script = base_script("TEST6_LEAK")
    script["script"]["title_hi"] = "वो #Contrarian पल"
    report = run_bundle(base_bundle("leak", script=script), "leak")
    leak = find(report, "public leak scan")
    assert leak.status == FAIL, f"a hashtag passed the leak scan ({leak.measured})"
    assert "#Contrarian" in leak.detail, leak.detail
    return leak.measured


@check("the render's own id in public text fails the leak scan by value")
def t_render_id_leak_is_caught():
    bundle = base_bundle("id_leak")
    render_id = bundle["render_id"]
    script = base_script(render_id)
    script["script"]["title_hi"] = f"{render_id} के बारे में सच"
    bundle["script"] = script
    report = run_bundle(bundle, "id_leak")
    leak = find(report, "public leak scan")
    assert leak.status == FAIL, f"a render id passed the leak scan ({leak.measured})"
    return leak.measured


@check("Carlos in the script fails the names scan")
def t_name_is_caught():
    script = base_script("TEST6_NAME")
    script["script"]["beats"][1]["line_hi"] = "Carlos ने तुम्हें देखा भी नहीं।"
    report = run_bundle(base_bundle("name", script=script), "name")
    names = find(report, "names present")
    assert names.status == FAIL, f"a name passed the scan ({names.measured})"
    assert "carlos" in names.detail.lower(), names.detail
    return names.measured


@check("a bad title fails the Title Score, and a good one passes it")
def t_title_score_gate():
    cfg = config.load()
    # The suite scores with the harvested phrase list (Phase 7), so the test
    # does too: without phrases the 35 search points are 0 by design - a title
    # cannot be good because a phrase list was missing.
    phrases = ["लोग तुम्हें क्यों नज़रअंदाज़ करते हैं"]
    good = titlescore.score("लोग तुम्हें क्यों नज़रअंदाज़ करते हैं", cfg,
                            phrases=phrases, footage_words=["फ़ोन"])
    no_phrases = titlescore.score("लोग तुम्हें क्यों नज़रअंदाज़ करते हैं", cfg,
                                  footage_words=["फ़ोन"])
    bad = titlescore.score("A" * 70, cfg, phrases=phrases, footage_words=[])
    assert good["pass"], f"a good title scored {good['total']}"
    assert not no_phrases["pass"], ("a title scored without a phrase list must not "
                                    f"clear the gate ({no_phrases['total']})")
    assert not bad["pass"], f"a Latin 70-character title scored {bad['total']}"
    report = run_bundle(base_bundle("title", script=base_script(
        "TEST6_TITLE", title="A" * 70)), "title")
    title = find(report, "title score")
    assert title.status == FAIL, f"a bad title passed the gate ({title.measured})"
    return (f"good {good['total']}/100, without a phrase list {no_phrases['total']}/100, "
            f"bad {bad['total']}/100 -> blocked")


@check("a good render passes every blocking check")
def t_good_render_passes_blocking():
    report = run_bundle(base_bundle("good"), "good")
    failed = [c.name for c in report.checks
              if c.kind == "blocking" and c.status == FAIL]
    assert not failed, f"blocking checks failed on a good render: {failed}"
    assert report.cleared, "a clean render was not cleared"
    return f"{len(report.blocking)} blocking checks, all passed"


@check("the real render from Phase 5 passes every blocking check")
def t_real_render_passes():
    from antar.checks import load_bundle

    cfg = config.load()
    try:
        bundle = load_bundle(cfg)
    except Exception as exc:
        raise Skipped(
            "the finished render is packed in /home/user/ANTAR_VIDEOS.zip and "
            "deleted from the workshop, so there is no video here to check "
            f"({exc}). Extract ANTAR_0001_lane-b-pilot.mp4 into output/video "
            "and this test runs for real.") from exc
    folder = work() / "real"
    folder.mkdir(parents=True, exist_ok=True)
    assert not bundle["render_id"].upper().startswith("TEST"), \
        f"the check picked up a test fixture: {bundle['render_id']}"
    report = run_on(cfg, bundle, work=folder, out_dir=folder)
    failed = [f"{c.name}: {c.measured}" for c in report.checks
              if c.kind == "blocking" and c.status == FAIL]
    assert not failed, f"the built video is blocked: {failed}"
    return (f"{bundle['render_id']}: {len(report.blocking)} blocking checks passed, "
            f"score {report.score['total']}/100 measured")


# ------------------------------------------------------------------- warnings

@check("quiet audio warns on loudness without blocking")
def t_quiet_audio_warns():
    report = run_bundle(base_bundle("quiet", audio_level="0.002"), "quiet")
    loud = find(report, "loudness")
    assert loud.status in (WARN, FAIL), f"very quiet audio read {loud.measured}"
    assert not report.blocked_from_upload, "a loudness warning blocked the upload"
    return f"loudness {loud.measured} - warning, not a block"


@check("a beat longer than five seconds warns")
def t_long_beat_warns():
    report = run_bundle(base_bundle("slow", seconds=22.0, holds=[9.0, 6.0, 7.0]), "slow")
    beat = find(report, "beat length")
    assert beat.status == WARN, f"a 9s beat read {beat.measured}"
    return beat.measured


@check("a clip used more than twice across the vault warns")
def t_clip_reuse_warns():
    bundle = base_bundle("reuse")
    for entry in bundle["vault"]["clips"].values():
        entry["uses"] = 3
    report = run_bundle(bundle, "reuse")
    reuse = find(report, "clip reuse")
    assert reuse.status == WARN, f"a clip on its third use read {reuse.measured}"
    return reuse.measured


@check("a payoff that ends long before the video does warns")
def t_early_peak_warns():
    bundle = base_bundle("early_peak")
    bundle["audio"]["track"]["payoff_at"] = 2.0
    bundle["script"]["script"]["peak_line"] = 1
    report = run_bundle(bundle, "early_peak")
    peak = find(report, "peak position")
    assert peak.status == WARN, f"an early payoff read {peak.measured}"
    return peak.measured


@check("a script with no open question warns on the micro-loop")
def t_no_micro_loop_warns():
    script = base_script("TEST6_FLAT", lines=[
        "तुम बैठे रहते हो और वो चला जाता है।",
        "तुम्हारा फ़ोन मेज़ पर पड़ा रहता है।",
        "वो वापस नहीं आता।",
    ])
    report = run_bundle(base_bundle("flat", script=script), "flat")
    micro = find(report, "micro-loop")
    assert micro.status == WARN, f"a flat script read {micro.measured}"
    return micro.measured


# ------------------------------------------------------------- honest gaps

@check("a rule that cannot be measured says so, and is not a pass")
def t_unmeasurable_is_not_a_pass():
    bundle = base_bundle("noaudio")
    bundle["audio"] = None
    video = bundle["video"]
    silent = work() / "silent.mp4"
    subprocess.run([FF, "-hide_banner", "-v", "error", "-i", str(video),
                    "-an", "-c:v", "copy", "-y", str(silent)], capture_output=True)
    bundle["video"] = silent
    report = run_bundle(bundle, "noaudio")
    audio = find(report, "audio start")
    assert audio.status == UNAVAILABLE, f"no audio read as {audio.status}"
    assert not audio.passed, "an unmeasurable rule was counted as a pass"
    assert not report.blocked_from_upload, "an unmeasurable rule blocked the upload"
    counts = report.counts()
    assert counts[UNAVAILABLE] >= 1, counts
    return f"audio start {audio.status} - reported, not faked"


@check("the scorecard withholds what it cannot measure and refuses the unlock")
def t_withheld_points_block_the_unlock():
    """
    What "cannot be measured" looks like changes as the phases land:

      - Phase 6: withheld is in Details (no title score yet) and Distinctness
        (no history yet); the unlock is refused;
      - Phase 7: withheld shrinks as the title score lands;
      - Phase 10: with history on file, Distinctness becomes measurable and
        withhold moves to whatever the synthetic bundle did not provide.

    The test asserts the shape of the rule rather than the exact numbers:
    withheld >= 1, the unlock is refused, the missing list is named, the
    measured total agrees with the sum of categories.
    """
    report = run_bundle(base_bundle("withheld"), "withheld")
    score = report.score
    assert score["withheld"] >= 1, f"only {score['withheld']} points withheld"
    assert score["missing"], score  # the rule says what is missing
    unlocked, why = report.unlocks()
    assert not unlocked, "the unlock was awarded on a partial score"
    assert "cannot be measured yet" in why or "below" in why, why
    measured_total = sum(c["earned"] for c in score["categories"])
    assert abs(measured_total - score["total"]) < 0.51, (measured_total, score["total"])
    return (f"{score['total']}/100 measured, {score['withheld']} withheld - "
            f"missing: {', '.join(score['missing'])}")


@check("a blocking failure blocks the unlock whatever the score says")
def t_blocking_failure_blocks_unlock():
    report = run_bundle(base_bundle("blocked", colour="black"), "blocked")
    unlocked, why = report.unlocks()
    assert not unlocked, "a blocked video was unlocked"
    assert "blocked by" in why, why
    return why


# ------------------------------------------------------------------ the scans

@check("the leak scan reads lane slugs, stage words and file names")
def t_leak_shapes():
    hits = textscan.leaks({
        "title": "lane-b की बात",
        "body": "see plan.mp4 for details",
        "note": "phase 5 में लिखा",
        "clean": "तुम्हारा फ़ोन मेज़ पर पड़ा है।",
    })
    found = {h["found"] for h in hits}
    assert "lane-b" in found, found
    assert "mp4" in found, found
    assert "phase 5" in found, found
    assert not [h for h in hits if h["where"] == "clean"], "a clean Hindi line was flagged"
    return f"{len(hits)} hits: {', '.join(sorted(found))}"


@check("the names scan catches names in both scripts")
def t_name_scripts():
    latin = textscan.names({"a": "Carlos came back."})
    hindi = textscan.names({"b": "कार्लोस ने कहा।"})
    assert any(h["kind"] == "forbidden name" for h in latin), latin
    assert any(h["kind"] == "forbidden name" for h in hindi), hindi
    return f"latin {latin[0]['found']}, hindi {hindi[0]['found']}"


@check("the report counts are the checks that ran")
def t_report_counts():
    report = run_bundle(base_bundle("counts"), "counts")
    counts = report.counts()
    assert sum(counts.values()) == len(report.checks), (counts, len(report.checks))
    assert len(report.blocking) == 7, f"{len(report.blocking)} blocking checks"
    assert len(report.warnings) == 11, f"{len(report.warnings)} warning checks"
    assert len(report.checks) == 18, f"{len(report.checks)} checks in total"
    return (f"{counts['PASS']} pass, {counts['WARN']} warn, {counts['FAIL']} fail, "
            f"{counts['UNAVAILABLE']} unmeasurable")


@check("the check result is written to disk and reads back")
def t_result_is_written():
    bundle = base_bundle("written")
    folder = work() / "written"
    folder.mkdir(parents=True, exist_ok=True)
    report = run_bundle(bundle, "written")
    path = folder / f"{report.render_id}_check.json"
    assert path.exists(), f"nothing written to {path}"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["render_id"] == report.render_id
    assert len(payload["checks"]) == len(report.checks)
    assert "scorecard" in payload and "blocked_from_upload" in payload
    return f"{path.name}: {len(payload['checks'])} checks, score {payload['scorecard']['total']}"


ALL = [
    t_black_video_is_caught, t_bright_video_is_caught, t_late_audio_is_caught,
    t_duration_limits_are_enforced, t_internal_label_is_caught,
    t_render_id_leak_is_caught, t_name_is_caught, t_title_score_gate,
    t_good_render_passes_blocking, t_real_render_passes,
    t_quiet_audio_warns, t_long_beat_warns, t_clip_reuse_warns,
    t_early_peak_warns, t_no_micro_loop_warns,
    t_unmeasurable_is_not_a_pass, t_withheld_points_block_the_unlock,
    t_blocking_failure_blocks_unlock,
    t_leak_shapes, t_name_scripts, t_report_counts, t_result_is_written,
]


def run_all(verbose: bool = True) -> bool:
    RESULTS.clear()
    SKIPPED.clear()
    if verbose:
        print()
        print("  ANTAR - PHASE 6 SELF TEST")
        print("  " + "-" * 62)
    started = time.time()
    for test in ALL:
        test(verbose=verbose)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    if verbose:
        print("  " + "-" * 62)
        summary = f"  {passed}/{total} passed in {time.time() - started:.2f}s"
        if SKIPPED:
            summary += f", {len(SKIPPED)} skipped (needs a file that is packed away)"
        print(summary)
        for name, why in SKIPPED:
            print(f"    [SKIP] {name}: {why[:96]}")
        if passed != total:
            print("  failing:")
            for name, ok, detail in RESULTS:
                if not ok:
                    print(f"    - {name}: {detail}")
    return passed == total


if __name__ == "__main__":
    raise SystemExit(0 if run_all() else 1)
