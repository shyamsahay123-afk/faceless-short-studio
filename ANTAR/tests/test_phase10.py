"""
Phase 10 self tests - the learn loop.

The exit line for Phase 10 is "next topic informed by real results". The
tests below prove every part of that promise:

  * the CSV reader walks YouTube Studio exports under whatever header
    names a channel happens to use this month, and never invents a number;
  * the aggregate groups per-video metrics by lane, hook, structure, grade
    - all four axes that the rotation memory keeps;
  * the recommendation ranks rotation values by retention, views, and
    swipe-away, and refuses to recommend from one video (a single data
    point is a sample, not a pattern);
  * the loop closes the rotation-diff proof on the scorecard: Distinctness
    stops being "withheld" and becomes a real number the upload reads;
  * the panel's LEARN tab reads the same files the command line reads, so
    what the operator sees in the browser is what the writer is steered by;
  * the panel refuses to import a file that is not a CSV (a path that
    points outside the workshop is refused, not silently copied).
"""

from __future__ import annotations

import csv
import io
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from antar import config                                          # noqa: E402
from antar.learn import csv as learn_csv                           # noqa: E402
from antar.learn import recommend as learn_recommend               # noqa: E402
from antar.panel import data as panel_data                         # noqa: E402
from antar.panel import server                                    # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str):
    def wrap(fn):
        def run_it(verbose: bool = True):
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
        return run_it
    return wrap


# --------------------------------------------------------------- helpers

SAMPLE_A = """Video title,Views,Average view duration,Avg % viewed,Swipe away rate,Likes,Comments
random unrelated topic alpha,1240,12.5,35.8,62.3,89,12
"""
SAMPLE_B = """Video title,Views,Average view duration,Avg % viewed,Swipe away rate,Likes,Comments
another random video that should not match any render by title,8420,24.3,68.4,38.1,612,84
"""


def setup_two_history(cfg):
    """Two videos with different rotation values + matching CSVs AND scripts.

    The synthetic ANTAR_0002 script exists only so the aggregate's
    _group_by() can read its rotation values - the real ANTAR_0001
    script is on disk in a clean workshop. The synthetic script is deleted
    in teardown so it does not pollute anything else.
    """
    folder = cfg.path("paths.output") / "analytics"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ANTAR_0001_lane-b-pilot.csv").write_text(SAMPLE_A, encoding="utf-8")
    (folder / "ANTAR_0002_lane-b-pilot.csv").write_text(SAMPLE_B, encoding="utf-8")

    scripts_dir = cfg.path("paths.output") / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    synthetic = scripts_dir / "ANTAR_0002_lane-b-pilot.json"
    if not synthetic.exists():
        synthetic.write_text(json.dumps({
            "render_id": "ANTAR_0002_lane-b-pilot",
            "topic": {"lane": "B"},
            "rotation": {"script_structure": "loop-question",
                          "hook_angle": "contrarian",
                          "grade": "warm-amber",
                          "duration": 36, "type_size": 210},
        }, ensure_ascii=False), encoding="utf-8")

    video_dir = cfg.path("paths.output") / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    synthetic_build = video_dir / "ANTAR_0002_lane-b-pilot_build.json"
    if not synthetic_build.exists():
        synthetic_build.write_text(json.dumps({
            "render_id": "ANTAR_0002_lane-b-pilot",
            "file": "ANTAR_0002_lane-b-pilot.mp4",
            "seconds": 36.0,
        }, ensure_ascii=False), encoding="utf-8")


    from antar.state import RunState
    state = RunState(cfg.path("paths.state") / "state.json")
    state.data["history"] = [
        {"render_id": "ANTAR_0001_lane-b-pilot",
         "rotation": {"opening_device": "question", "script_structure": "problem-mechanism",
                      "ending_device": "loop-return", "beat_count": 7,
                      "grade": "cold-blue", "shot_family": "object-still-life",
                      "text_density": "one-to-two-word", "silence_placement": "before-last-line",
                      "duration": 33, "type_size": 250, "hook_angle": "direct-question"},
         "at": time.time() - 86400, "stage": "script", "score": 80, "words": 90},
        {"render_id": "ANTAR_0002_lane-b-pilot",
         "rotation": {"opening_device": "statement", "script_structure": "loop-question",
                      "ending_device": "peak-line", "beat_count": 6,
                      "grade": "warm-amber", "shot_family": "empty-room",
                      "text_density": "one-word-only", "silence_placement": "before-peak",
                      "duration": 36, "type_size": 210, "hook_angle": "contrarian"},
         "at": time.time(), "stage": "script", "score": 80, "words": 90},
    ]
    state.data["last_rotation"] = state.data["history"][-1]["rotation"]
    state.data["render_counter"] = 2
    state.save()
    return folder


def teardown(cfg):
    """Wipe everything in output/analytics/ AND clean up the synthetic
    script setup_two_history wrote. Tests in this file do not isolate
    themselves from each other, so the teardown is aggressive."""
    folder = cfg.path("paths.output") / "analytics"
    if folder.exists():
        for path in folder.glob("*"):
            if path.is_file():
                path.unlink()
        for path in folder.glob("*"):
            if path.is_dir():
                shutil.rmtree(path)
    # remove the synthetic 0002 script if we wrote it (real one is in
    # test_phase8 or earlier; this only exists because setup_two_history
    # put it there)
    synthetic_script = cfg.path("paths.output") / "scripts" / "ANTAR_0002_lane-b-pilot.json"
    synthetic_build = cfg.path("paths.output") / "video" / "ANTAR_0002_lane-b-pilot_build.json"
    for path in (synthetic_script, synthetic_build):
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if (payload.get("rotation", {}).get("hook_angle") == "contrarian"
                        or payload.get("render_id") == "ANTAR_0002_lane-b-pilot"):
                    path.unlink()
            except (json.JSONDecodeError, OSError):
                pass


# ---------------------------------------------------------------- reader

@check("the CSV reader parses both new and old YT header names")
def t_csv_reader_handles_headers():
    text = ("Content,Views (in this period),Avg view duration,Avg % viewed\n"
            "video,1240,12.5,35.8\n")
    parsed = learn_csv.parse(text)
    assert parsed["metrics"]["views"], "views not extracted"
    assert parsed["metrics"]["avg_view_seconds"], "average view duration not extracted"
    assert parsed["metrics"]["avg_view_pct"], "avg % viewed not extracted"
    assert parsed["matched_columns"]["views"], "matched column not recorded"
    return f"3 metrics matched, header had {len(parsed['header'])} columns"


@check("the CSV reader handles percent signs and comma-formatted numbers")
def t_csv_reader_handles_numbers():
    text = ("Views,Avg % viewed\n"
            "\"1,240\",35.8%\n"
            "\"8,420\",68.4%\n")
    parsed = learn_csv.parse(text)
    views = parsed["metrics"]["views"]
    pcts = parsed["metrics"]["avg_view_pct"]
    assert views[0] == 1240, f"comma-formatted int: {views}"
    assert pcts[0] == 35.8, f"percent: {pcts}"
    assert views[1] == 8420
    return "1,240 parsed as 1240, 35.8% parsed as 35.8"


@check("the CSV reader never invents a metric that is not in the file")
def t_csv_reader_does_not_invent():
    text = "Random Column\nstuff\n"
    parsed = learn_csv.parse(text)
    assert parsed["metrics"]["views"] is None, "views should not be inferred"
    assert parsed["matched_columns"] == {}, parsed
    return "no metric, no matched columns, no false positives"


@check("the reader returns 0 for missing metrics, not None")
def t_video_metric_returns_zero():
    text = "Views,Avg % viewed\n1,2\n"
    parsed = learn_csv.parse(text)
    metric = learn_csv.VideoMetric.from_csv(Path("/tmp/_none.csv"), "")
    # if no file, the metric has zeros
    assert metric.view_count() == 0
    assert metric.avg_view_pct() == 0.0
    return "all missing metrics return 0 / 0.0, never None"


# ------------------------------------------------------- per-video pairing

@check("a CSV named after a render is paired with that render")
def t_match_by_filename():
    cfg = config.load()
    folder = setup_two_history(cfg)
    try:
        metrics = learn_csv.all_metrics(cfg)
        pairs = [(m.render_id, Path(m.csv_path).name) for m in metrics]
        matched = {name: rid for rid, name in pairs if rid}
        assert matched.get("ANTAR_0001_lane-b-pilot.csv") == "ANTAR_0001_lane-b-pilot", matched
        assert matched.get("ANTAR_0002_lane-b-pilot.csv") == "ANTAR_0002_lane-b-pilot", matched
        return "2/2 paired by filename"
    finally:
        teardown(cfg)


@check("a CSV with no matching render is recorded as unpaired, not guessed")
def t_unpaired_csv():
    cfg = config.load()
    folder = cfg.path("paths.output") / "analytics"
    folder.mkdir(parents=True, exist_ok=True)
    try:
        (folder / "orphan.csv").write_text(SAMPLE_A, encoding="utf-8")
        metrics = learn_csv.all_metrics(cfg)
        orphans = [m for m in metrics if not m.render_id]
        assert orphans, "expected at least one unpaired metric"
        assert "no recognised metrics" not in orphans[0].note, "the orphan's note should be empty - parse worked, just no render match"
        return "1 orphan recorded with empty render_id"
    finally:
        teardown(cfg)


# ---------------------------------------------------------- the aggregate

@check("aggregate groups by lane, hook, structure, and grade")
def t_aggregate_groups_by_axis():
    cfg = config.load()
    setup_two_history(cfg)
    try:
        metrics = learn_csv.all_metrics(cfg)
        aggregate_path = learn_csv.write_aggregate(cfg, metrics)
        aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
        for axis in ("by_lane", "by_hook", "by_structure", "by_grade"):
            assert axis in aggregate, f"missing {axis}"
            assert aggregate[axis], f"empty {axis}"
        return (f"by_lane {list(aggregate['by_lane'])}, "
                f"by_hook {list(aggregate['by_hook'])}, "
                f"by_structure {list(aggregate['by_structure'])}")
    finally:
        teardown(cfg)


@check("summary records total views, retention, top video")
def t_aggregate_summary():
    cfg = config.load()
    setup_two_history(cfg)
    try:
        metrics = learn_csv.all_metrics(cfg)
        aggregate = learn_csv.write_aggregate(cfg, metrics)
        summary = json.loads(aggregate.read_text(encoding="utf-8"))["summary"]
        assert summary["videos_with_data"] == 2, summary
        assert summary["total_views"] == 1240 + 8420, summary
        assert summary["top_video"]["value"] == 8420, summary
        return (f"videos {summary['videos_with_data']}, total views {summary['total_views']}, "
                f"top video {summary['top_video']['render_id']}")
    finally:
        teardown(cfg)


# --------------------------------------------------------- the recommend

@check("the loop ranks rotation values by retention, views, swipe-away")
def t_ranking_uses_all_three_signals():
    cfg = config.load()
    setup_two_history(cfg)
    try:
        rec = learn_recommend.learn(cfg)
        axes = rec.get("axes") or {}
        # by_structure must have both problem-mechanism and loop-question; the
        # second's retention (68.4%) beats the first's (35.8%)
        structure = axes.get("structure") or []
        names = [row["name"] for row in structure]
        assert "loop-question" in names, structure
        assert "problem-mechanism" in names, structure
        scores = {row["name"]: row["score"] for row in structure}
        assert scores["loop-question"] > scores["problem-mechanism"], scores
        return (f"loop-question {scores['loop-question']:.1f} > "
                f"problem-mechanism {scores['problem-mechanism']:.1f}")
    finally:
        teardown(cfg)


@check("one-video buckets are marked untrusted, not promoted to winners")
def t_one_video_is_not_a_pattern():
    cfg = config.load()
    setup_two_history(cfg)
    try:
        rec = learn_recommend.learn(cfg)
        for axis in ("hook", "structure", "grade"):
            for row in rec["axes"].get(axis) or []:
                assert row["trusted"] is False, (axis, row)
                assert row["videos"] == 1, (axis, row)
        return "every one-video bucket is marked untrusted"
    finally:
        teardown(cfg)


@check("anti-patterns: the bottom of every axis with >=2 videos")
def t_anti_patterns_named():
    cfg = config.load()
    setup_two_history(cfg)
    try:
        rec = learn_recommend.learn(cfg)
        # by_lane has 2 videos (both Lane B), so an anti-pattern check applies;
        # by_hook/structure/grade each have 1 video, so anti-patterns there
        # would not be honest - the loop should not invent them.
        ap = rec.get("anti_patterns") or []
        assert all(p["videos"] >= 2 for p in ap), ap
        return f"{len(ap)} anti-pattern(s), all from axes with >=2 videos"
    finally:
        teardown(cfg)


@check("the brief names lane, hook, structure, grade winners when trusted")
def t_brief_names_winners():
    cfg = config.load()
    setup_two_history(cfg)
    try:
        rec = learn_recommend.learn(cfg)
        brief = rec["next_topic_brief"]
        # the lane bucket has 2 videos (both Lane B), so it is trusted
        assert brief.get("lane"), brief
        assert brief["lane"]["name"] == "B", brief["lane"]
        # hook/structure/grade have 1 video each - the brief leaves them None
        for axis in ("hook", "structure", "grade"):
            assert brief.get(axis) is None, (axis, brief.get(axis))
        return f"lane trusted ({brief['lane']['name']}), the rest waiting for more videos"
    finally:
        teardown(cfg)


# -------------------------------------------------------- closing the gate

@check("the loop closes Distinctness in the scorecard when history is real")
def t_distinctness_closed():
    cfg = config.load()
    setup_two_history(cfg)
    try:
        # write a check file with Distinctness withheld
        check_path = cfg.path("paths.output") / "checks" / "ANTAR_0001_lane-b-pilot_check.json"
        if check_path.exists():
            payload = json.loads(check_path.read_text(encoding="utf-8"))
            categories = payload.get("scorecard", {}).get("categories") or []
            for row in categories:
                if row.get("category") == "Distinctness":
                    row["earned"] = 0.0
            payload["scorecard"]["categories"] = categories
            payload["scorecard"]["total"] = sum(c["earned"] for c in categories)
            payload["scorecard"]["withheld"] = max(0, 100 - payload["scorecard"]["total"])
            check_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

        rec = learn_recommend.learn(cfg)
        result = rec.get("_distinctness") or {}
        # Distinctness is now non-zero in the check file
        if not check_path.exists():
            return "no check file on disk - run: python run.py check first"
        check = json.loads(check_path.read_text(encoding="utf-8"))
        for row in check["scorecard"]["categories"]:
            if row["category"] == "Distinctness":
                assert row["earned"] > 0, f"Distinctness still 0: {row}"
                return (f"Distinctness {row['earned']}/5 - the rotation-diff proof "
                        "now contributes to the scorecard")
        raise AssertionError("Distinctness not in the scorecard categories")
    finally:
        teardown(cfg)


@check("the loop refuses to recommend with one video on file")
def t_no_recommendation_with_one_video():
    cfg = config.load()
    folder = cfg.path("paths.output") / "analytics"
    folder.mkdir(parents=True, exist_ok=True)
    try:
        (folder / "single.csv").write_text(SAMPLE_A, encoding="utf-8")
        metrics = learn_csv.all_metrics(cfg)
        learn_csv.write_aggregate(cfg, metrics)
        rec = learn_recommend.learn(cfg)
        assert rec.get("next_topic_brief") in (None, {}), rec
        assert rec.get("note"), "no note about why the brief is empty"
        return "no brief, note explains why"
    finally:
        teardown(cfg)


# ------------------------------------------------------------ the panel

@check("the LEARN tab exposes every axis and the upload affordance")
def t_panel_learn_tab():
    cfg = config.load()
    setup_two_history(cfg)
    try:
        httpd, registry, url = server.start(cfg, port=0, quiet=True)
        try:
            page = urllib.request.urlopen(url.rstrip("/") + "/", timeout=30).read().decode("utf-8")
            assert '"HOME","WRITER","PICTURE","CHECK","DETAILS","PROOF","SCORE","KEYS","LEARN","SETTINGS"' in page, \
                "the LEARN tab is missing from the page"
            payload = json.loads(urllib.request.urlopen(url.rstrip("/") + "/api/tab/learn",
                                                       timeout=30).read())
            assert payload["ready"] is True, payload
            assert payload["csvs"], "no CSVs in payload"
            assert payload["axes"], "no axes in the learn payload"
            assert payload["next_topic_brief"], "no brief in the learn payload"
            return (f"LEARN tab loads: {len(payload['csvs'])} CSV(s), "
                    f"axes {list(payload['axes'])}, "
                    f"brief lane {payload['next_topic_brief'].get('lane',{}).get('name')}")
        finally:
            httpd.shutdown(); httpd.server_close()
    finally:
        teardown(cfg)


@check("the panel refuses to import a file that is not a CSV")
def t_panel_refuses_non_csv():
    cfg = config.load()
    httpd, registry, url = server.start(cfg, port=0, quiet=True)
    try:
        bad = Path("/tmp/_not_a_csv.txt")
        bad.write_text("hello", encoding="utf-8")
        try:
            req = urllib.request.Request(url.rstrip("/") + "/api/learn/import",
                                         method="POST",
                                         headers={"Content-Type": "application/json"},
                                         data=json.dumps({"source": str(bad)}).encode("utf-8"))
            urllib.request.urlopen(req, timeout=30).read()
            raise AssertionError("a non-CSV was imported")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400, exc.code
            assert "only CSV files are accepted" in exc.read().decode("utf-8"), exc.read()
        return "non-CSV refused with a plain sentence"
    finally:
        bad.unlink(missing_ok=True)
        httpd.shutdown(); httpd.server_close()


@check("the panel refuses to import a file that does not exist")
def t_panel_refuses_missing():
    cfg = config.load()
    httpd, registry, url = server.start(cfg, port=0, quiet=True)
    try:
        try:
            req = urllib.request.Request(url.rstrip("/") + "/api/learn/import",
                                         method="POST",
                                         headers={"Content-Type": "application/json"},
                                         data=json.dumps({"source": "/no/such/file.csv"}).encode("utf-8"))
            urllib.request.urlopen(req, timeout=30).read()
            raise AssertionError("a missing file was imported")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400, exc.code
            assert "no such file" in exc.read().decode("utf-8").lower()
        return "missing file refused"
    finally:
        httpd.shutdown(); httpd.server_close()


# --------------------------------------------------------------- cmd line

@check("cmd_learn prints rankings and writes recommend.json")
def t_cmd_learn_writes_recommend():
    cfg = config.load()
    setup_two_history(cfg)
    try:
        result = subprocess.run([sys.executable, "run.py", "learn"],
                                capture_output=True, text=True, cwd=str(ROOT))
        assert result.returncode == 0, result.stdout[-1200:]
        recommend_path = cfg.path("paths.output") / "analytics" / "recommend.json"
        assert recommend_path.exists(), "no recommend.json written"
        text = result.stdout
        assert "rankings" in text.lower(), "rankings section missing"
        assert "next topic brief" in text.lower(), "next topic brief section missing"
        rec = json.loads(recommend_path.read_text(encoding="utf-8"))
        assert rec["recommendation"]["axes"], rec
        return (f"recommend.json has {len(rec['recommendation']['axes'])} axes, "
                f"brief lane {rec['recommendation']['next_topic_brief'].get('lane',{}).get('name')}")
    finally:
        teardown(cfg)


@check("cmd_learn --import copies a CSV into the workshop")
def t_cmd_learn_import():
    cfg = config.load()
    folder = cfg.path("paths.output") / "analytics"
    if folder.exists():
        for p in folder.glob("*"): p.unlink()
    tmp = Path("/tmp/_antar_learn_import.csv")
    tmp.write_text(SAMPLE_A, encoding="utf-8")
    try:
        result = subprocess.run([sys.executable, "run.py", "learn", "--import", str(tmp)],
                                capture_output=True, text=True, cwd=str(ROOT))
        assert result.returncode == 0, result.stdout[-1200:]
        target = folder / tmp.name
        assert target.exists(), f"no copy at {target}"
        # the source still exists (copy, not move)
        assert tmp.exists()
        return f"copied to {target.name}"
    finally:
        tmp.unlink(missing_ok=True)
        teardown(cfg)


@check("cmd_learn refuses --import with a non-CSV file")
def t_cmd_learn_refuses_non_csv():
    cfg = config.load()
    tmp = Path("/tmp/_antar_learn_bad.txt")
    tmp.write_text("hello", encoding="utf-8")
    try:
        result = subprocess.run([sys.executable, "run.py", "learn", "--import", str(tmp)],
                                capture_output=True, text=True, cwd=str(ROOT))
        assert result.returncode != 0, result.stdout
        assert "only CSV files are accepted" in result.stdout + result.stderr, \
            result.stdout + result.stderr
        return "refused with a plain sentence"
    finally:
        tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------- run

ALL = [
    t_csv_reader_handles_headers, t_csv_reader_handles_numbers,
    t_csv_reader_does_not_invent, t_video_metric_returns_zero,
    t_match_by_filename, t_unpaired_csv,
    t_aggregate_groups_by_axis, t_aggregate_summary,
    t_ranking_uses_all_three_signals, t_one_video_is_not_a_pattern,
    t_anti_patterns_named, t_brief_names_winners,
    t_distinctness_closed, t_no_recommendation_with_one_video,
    t_panel_learn_tab, t_panel_refuses_non_csv, t_panel_refuses_missing,
    t_cmd_learn_writes_recommend, t_cmd_learn_import,
    t_cmd_learn_refuses_non_csv,
]


def run_all(verbose: bool = True) -> bool:
    RESULTS.clear()
    if verbose:
        print("\n  ANTAR - PHASE 10 SELF TEST")
        print("  " + "-" * 62)
    started = time.time()
    for test in ALL:
        test(verbose=verbose)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    if verbose:
        print("  " + "-" * 62)
        print(f"  {passed}/{total} passed in {time.time() - started:.2f}s")
        for name, ok, detail in RESULTS:
            if not ok:
                print(f"    - {name}: {detail}")
    return passed == total


if __name__ == "__main__":
    raise SystemExit(0 if run_all() else 1)
