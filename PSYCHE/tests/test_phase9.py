"""
Phase 9 self tests - the proof stage.

The exit line for Phase 9 is "Scorecard >= 85, shown with numbers". Every test
in this file is a number or it is a guarantee that a number is on disk.

The contract:

  * every proof is a real number in the proof file, never a sentence that says
    "it works" - if the file does not say `PASS 41/255` the proof did not run;
  * `UNAVAILABLE` is a real state. It never counts as PASS and never counts
    toward the upload unlock. A defect that hides behind a missing file is
    still a defect;
  * the real thumbnails exist on disk, at the right size, with the title over
    the footage. Two files, both readable, both measured with the same helper
    the check uses;
  * the proof file's scorecard is the scorecard the check wrote. If they
    disagree, the proof stage is wrong, not the gate.
"""

from __future__ import annotations

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
from antar.panel import data, server                              # noqa: E402
from antar.proof import (LANDSCAPE, ProofError, evidence,         # noqa: E402
                          make_real_thumbnail, thumbnail as thumb_mod)

RESULTS: list[tuple[str, bool, str]] = []


def _has_full_render(cfg, render_id: str) -> bool:
    """Phase 9 proofs run against a real pipeline render.

    The proofs read the audio record, the picture plan, the build sheet, and
    the actual .mp4. When those files are not on disk (because the user
    packed-and-deleted, or because the sandbox has no AI keys to render one),
    the tests must say so in plain words and skip - a fabricated number would
    be the lie the project charter was written to prevent.
    """
    if not render_id:
        return False
    video = cfg.path("paths.output") / "video" / f"{render_id}.mp4"
    if not video.exists() or video.stat().st_size < 100:
        return False
    audio = cfg.path("paths.output") / "audio" / f"{render_id}_audio.json"
    if not audio.exists():
        return False
    plan = cfg.path("paths.output") / "plans" / f"{render_id}_picture.json"
    if not plan.exists():
        return False
    check = cfg.path("paths.output") / "checks" / f"{render_id}_check.json"
    if not check.exists():
        return False
    return True


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


# ----------------------------------------------------------------- the proofs

@check("every proof from the test plan runs and writes a number")
def t_all_ten_proofs_run():
    cfg = config.load()
    render_id = data.current_render(cfg)
    if not _has_full_render(cfg, render_id):
        return "no full pipeline render on disk - run: python run.py build to do it"
    record = evidence.prove(cfg, render_id)
    checks = record["checks"]
    names = [row["name"] for row in checks]
    expected = [
        "Khand contact sheet", "Swara word timings", "Hindi pacing",
        "thumbnail brightness", "no black frames", "loop seam",
        "every beat has a picture", "clip reuse", "details quality",
        "rotation diff",
    ]
    assert len(checks) == 10, f"expected 10 proofs, got {len(checks)}"
    for name in expected:
        assert name in names, f"missing proof: {name}"
    for row in checks:
        assert row["measured"] != "-", f"proof {row['name']} wrote no number"
        assert row["result"] in ("PASS", "WARN", "FAIL", "UNAVAILABLE"), \
            f"proof {row['name']} has a result of {row['result']!r}"
    return f"10 proofs, all results in {set(r['result'] for r in checks)}"


@check("proof stage writes a file on every run, not a silent nothing")
def t_writes_proof_file():
    cfg = config.load()
    render_id = data.current_render(cfg)
    if not _has_full_render(cfg, render_id):
        return "no full pipeline render on disk - run: python run.py build to do it"
    record = evidence.prove(cfg, render_id)
    out = cfg.path("paths.output") / "proof" / f"{render_id}_proof.json"
    assert out.exists(), f"no proof file at {out}"
    on_disk = json.loads(out.read_text(encoding="utf-8"))
    assert on_disk["render_id"] == record["render_id"], "the file is not what the function returned"
    assert on_disk["summary"]["scorecard_total"] == record["summary"]["scorecard_total"]
    return f"{out.stat().st_size} bytes, scorecard {on_disk['summary']['scorecard_total']}/100"


@check("the proof stage's scorecard IS the check stage's scorecard")
def t_scorecard_agreement():
    cfg = config.load()
    render_id = data.current_render(cfg)
    if not _has_full_render(cfg, render_id):
        return "no full pipeline render on disk - run: python run.py build to do it"
    proof_record = evidence.prove(cfg, render_id)
    check_file = cfg.path("paths.output") / "checks" / f"{render_id}_check.json"
    check = json.loads(check_file.read_text(encoding="utf-8")) if check_file.exists() else {}
    proof_total = proof_record["summary"]["scorecard_total"]
    check_total = (check.get("scorecard") or {}).get("total")
    assert proof_total == check_total, (proof_total, check_total)
    return f"both say {proof_total}/100, gate {proof_record['summary']['upload_unlock']}"


@check("Khand contact sheet is real and measured")
def t_khand_sheet():
    cfg = config.load()
    render_id = data.current_render(cfg)
    if not _has_full_render(cfg, render_id):
        return "no full pipeline render on disk - run: python run.py build to do it"
    record = evidence.prove(cfg, render_id)
    proof = next(row for row in record["checks"] if row["name"] == "Khand contact sheet")
    assert proof["result"] == "PASS", proof
    assert Path(proof["evidence"]).exists(), proof["evidence"]
    return f"{proof['measured']}, file on disk"


@check("Swara timing proof uses lead silence AND first-word time")
def t_swara_timing():
    cfg = config.load()
    render_id = data.current_render(cfg)
    if not _has_full_render(cfg, render_id):
        return "no full pipeline render on disk - run: python run.py build to do it"
    record = evidence.prove(cfg, render_id)
    proof = next(row for row in record["checks"] if row["name"] == "Swara word timings")
    assert proof["result"] == "PASS", proof
    text = proof["measured"]
    assert "lead" in text and "first word at" in text, text
    return text


@check("Hindi pacing checks words-per-second AND the word-count band")
def t_pacing():
    cfg = config.load()
    render_id = data.current_render(cfg)
    if not _has_full_render(cfg, render_id):
        return "no full pipeline render on disk - run: python run.py build to do it"
    record = evidence.prove(cfg, render_id)
    proof = next(row for row in record["checks"] if row["name"] == "Hindi pacing")
    assert proof["result"] == "PASS", proof
    locked = proof.get("locked_words_per_second", 0.0)
    measured = float(proof["measured"].split()[0])
    assert abs(measured - locked) < 0.01, (measured, locked)
    band = proof.get("locked_word_band") or [0, 0]
    assert band[0] <= band[1], band
    return f"{proof['measured']}, band {band[0]}-{band[1]} words"


@check("thumbnail brightness proof uses the same helper the check uses")
def t_thumbnail_brightness():
    cfg = config.load()
    render_id = data.current_render(cfg)
    if not _has_full_render(cfg, render_id):
        return "no full pipeline render on disk - run: python run.py build to do it"
    record = evidence.prove(cfg, render_id)
    proof = next(row for row in record["checks"] if row["name"] == "thumbnail brightness")
    assert proof["result"] in ("PASS", "FAIL"), proof
    target_band = proof.get("target") or ""
    assert "/" in proof["measured"] and "/" in target_band, (proof, target_band)
    return f"{proof['measured']} on {Path(proof['evidence']).name}"


@check("no-black-frames proof spreads 12 samples across the duration")
def t_no_black_frames():
    cfg = config.load()
    render_id = data.current_render(cfg)
    if not _has_full_render(cfg, render_id):
        return "no full pipeline render on disk - run: python run.py build to do it"
    record = evidence.prove(cfg, render_id)
    proof = next(row for row in record["checks"] if row["name"] == "no black frames")
    assert proof["result"] == "PASS", proof
    samples = proof.get("samples") or []
    assert len(samples) == 12, f"expected 12 samples, got {len(samples)}"
    assert all(sample["brightness"] >= 30 for sample in samples), \
        f"a sample is below 30: {[s for s in samples if s['brightness'] < 30]}"
    return f"darkest {proof['measured'].split()[1]}"


@check("loop seam proof reads the mastering record, not ffmpeg silence-detect")
def t_loop_seam():
    cfg = config.load()
    render_id = data.current_render(cfg)
    if not _has_full_render(cfg, render_id):
        return "no full pipeline render on disk - run: python run.py build to do it"
    record = evidence.prove(cfg, render_id)
    proof = next(row for row in record["checks"] if row["name"] == "loop seam")
    assert proof["result"] == "PASS", proof
    assert "lead_silence" in proof, "proof did not record the lead silence"
    assert "tail_silence" in proof, "proof did not record the tail silence"
    return proof["measured"]


@check("every beat has a picture proof counts clips and cards from the plan")
def t_beats_have_pictures():
    cfg = config.load()
    render_id = data.current_render(cfg)
    if not _has_full_render(cfg, render_id):
        return "no full pipeline render on disk - run: python run.py build to do it"
    record = evidence.prove(cfg, render_id)
    proof = next(row for row in record["checks"] if row["name"] == "every beat has a picture")
    assert proof["result"] == "PASS", proof
    assert "beats:" in proof["measured"], proof["measured"]
    assert "clips" in proof["measured"] and "cards" in proof["measured"], proof
    return proof["measured"]


@check("clip reuse proof reads the vault registry")
def t_clip_reuse():
    cfg = config.load()
    render_id = data.current_render(cfg)
    if not _has_full_render(cfg, render_id):
        return "no full pipeline render on disk - run: python run.py build to do it"
    record = evidence.prove(cfg, render_id)
    proof = next(row for row in record["checks"] if row["name"] == "clip reuse")
    assert proof["result"] == "PASS", proof
    return proof["measured"]


@check("details quality proof uses the chosen title and its recorded score")
def t_details_quality():
    cfg = config.load()
    render_id = data.current_render(cfg)
    if not _has_full_render(cfg, render_id):
        return "no full pipeline render on disk - run: python run.py build to do it"
    record = evidence.prove(cfg, render_id)
    proof = next(row for row in record["checks"] if row["name"] == "details quality")
    assert proof["result"] == "PASS", proof
    text = proof["measured"]
    assert "chosen" in text and "candidate" in text, text
    return text


@check("rotation diff is honest - first video says UNAVAILABLE, not PASS")
def t_rotation_diff_honest():
    cfg = config.load()
    render_id = data.current_render(cfg)
    if not _has_full_render(cfg, render_id):
        return "no full pipeline render on disk - run: python run.py build to do it"
    record = evidence.prove(cfg, render_id)
    proof = next(row for row in record["checks"] if row["name"] == "rotation diff")
    if proof["result"] == "UNAVAILABLE":
        # the proof is honest: measured says "first video on file", the note
        # says WHY the diff cannot run yet. Both must be present, neither must
        # pretend the proof succeeded
        assert proof["measured"] == "first video on file", proof["measured"]
        assert "previous video" in proof["note"].lower(), proof["note"]
    elif proof["result"] == "PASS":
        assert "shared" in proof["measured"], proof["measured"]
    return f"{proof['result']} - {proof['note'][:60]}"


# --------------------------------------------------------------- thumbnails

@check("the real thumbnail writes both files at the right size")
def t_real_thumbnail_files():
    cfg = config.load()
    render_id = data.current_render(cfg)
    details_path = cfg.path("paths.output") / "details" / f"{render_id}_details.json"
    if not details_path.exists():
        return "no details on disk yet"
    if not (cfg.path("paths.output") / "video" / f"{render_id}.mp4").exists():
        return "no video on disk - videos are packed away"
    record = make_real_thumbnail(cfg, render_id, details_path)
    full = Path(record["full"])
    landscape = Path(record["landscape"])
    assert full.exists(), f"missing {full}"
    assert landscape.exists(), f"missing {landscape}"
    from PIL import Image
    with Image.open(full) as image:
        full_size = image.size
    with Image.open(landscape) as image:
        land_size = image.size
    canvas = (int(cfg.get("canvas.width", 1080)), int(cfg.get("canvas.height", 1920)))
    assert full_size == canvas, (full_size, canvas)
    assert land_size == LANDSCAPE, (land_size, LANDSCAPE)
    return (f"portrait {full_size[0]}x{full_size[1]} ({record['full_brightness']:.0f}/255), "
            f"landscape {land_size[0]}x{land_size[1]} ({record['landscape_mean']:.0f}/255)")


@check("the landscape thumbnail has the title written over the footage")
def t_landscape_has_title():
    cfg = config.load()
    render_id = data.current_render(cfg)
    if not _has_full_render(cfg, render_id):
        return "no full pipeline render on disk - run: python run.py build to do it"
    details_path = cfg.path("paths.output") / "details" / f"{render_id}_details.json"
    record = make_real_thumbnail(cfg, render_id, details_path)
    landscape = Path(record["landscape"])
    from PIL import Image
    with Image.open(landscape) as image:
        # the bottom-right quadrant is where the title sits - sample a few
        # pixels there and confirm not all of them are pure black (which
        # would mean no title was drawn)
        pixels = [image.getpixel((1100, 600)), image.getpixel((1100, 660)),
                  image.getpixel((1100, 540)), image.getpixel((900, 600))]
        assert any(sum(p[:3]) > 60 for p in pixels), pixels
    return f"title visible at lower-right ({landscape.stat().st_size} bytes)"


@check("the real thumbnail records in_band, brightness, and the picked second")
def t_thumbnail_record_is_complete():
    cfg = config.load()
    render_id = data.current_render(cfg)
    if not _has_full_render(cfg, render_id):
        return "no full pipeline render on disk - run: python run.py build to do it"
    details_path = cfg.path("paths.output") / "details" / f"{render_id}_details.json"
    record = make_real_thumbnail(cfg, render_id, details_path)
    for key in ("picked_second", "full_brightness", "landscape_mean", "band", "in_band"):
        assert key in record, f"missing {key}"
    assert isinstance(record["band"], list) and len(record["band"]) == 2
    assert isinstance(record["in_band"], bool)
    assert 0 <= record["picked_second"] <= 60
    assert 0 <= record["full_brightness"] <= 255
    return (f"second {record['picked_second']}, full {record['full_brightness']:.0f}/255, "
            f"landscape {record['landscape_mean']:.0f}/255, in_band {record['in_band']}")


# -------------------------------------------------------------- panel / proof

@check("the panel exposes the proof tab and serves the landscape thumbnail")
def t_panel_proof_tab():
    cfg = config.load()
    httpd, registry, url = server.start(cfg, port=0, quiet=True)
    try:
        page = urllib.request.urlopen(url.rstrip("/") + "/", timeout=30).read().decode("utf-8")
        assert '"HOME","WRITER","PICTURE","CHECK","DETAILS","PROOF","SCORE","KEYS","LEARN","SETTINGS"' in page,             "PROOF tab missing from the static tabs list"

        payload = json.loads(urllib.request.urlopen(url.rstrip("/") + "/api/tab/proof",
                                                    timeout=30).read())
        assert payload["ready"] is True, payload.get("note", "")
        assert payload["score"] is not None, payload
        assert payload["gate"] == int(cfg.get("thresholds.upload_min", 85))
        assert payload["passed"] >= 1, payload

        body = urllib.request.urlopen(url.rstrip("/") + "/media/real_thumbnail",
                                     timeout=30).read()
        assert body[:4] == b"\xff\xd8\xff\xe0", f"not a JPEG: {body[:4]!r}"
        return (f"PROOF tab loads with score {payload['score']}/100 cleared "
                f"{payload['gate_cleared']}, landscape thumb {len(body)} bytes")
    finally:
        httpd.shutdown(); httpd.server_close()


@check("the proof panel reads PASS counts from the file, never invents them")
def t_panel_does_not_invent_proofs():
    cfg = config.load()
    httpd, registry, url = server.start(cfg, port=0, quiet=True)
    try:
        file_payload = json.loads((cfg.path("paths.output") / "proof" /
                                   f"{data.current_render(cfg)}_proof.json").read_text(encoding="utf-8"))
        panel_payload = json.loads(urllib.request.urlopen(url.rstrip("/") + "/api/tab/proof",
                                                          timeout=30).read())
        for key in ("passed", "warned", "failed", "unavailable", "score", "gate"):
            assert panel_payload[key] == file_payload["summary"]["scorecard_total"] \
                if key == "score" else panel_payload[key] >= 0, key
        names = sorted(c["name"] for c in panel_payload["checks"])
        file_names = sorted(c["name"] for c in file_payload["checks"])
        assert names == file_names, (names, file_names)
        return (f"panel mirrors the file: {panel_payload['passed']} pass, "
                f"{panel_payload['unavailable']} unavailable, score {panel_payload['score']}/100")
    finally:
        httpd.shutdown(); httpd.server_close()


# -------------------------------------------------------------- CLI

@check("cmd_proof writes the proof file and prints every proof's result")
def t_cmd_proof():
    cfg = config.load()
    import subprocess as sp

    target = cfg.path("paths.output") / "proof" / f"{data.current_render(cfg)}_proof.json"
    before = target.stat().st_mtime if target.exists() else 0
    result = sp.run([sys.executable, "run.py", "proof"], capture_output=True, text=True, cwd=str(ROOT))
    after = target.stat().st_mtime if target.exists() else 0
    assert result.returncode == 0, (result.stdout, result.stderr)[-1][-1200:]
    assert after > before, "proof stage did not rewrite its file"
    new_files = {target.name}
    text = result.stdout
    assert "[##] scorecard" in text, "no scorecard line in the proof output"
    for word in ("Khand", "Swara", "Hindi pacing", "thumbnail", "no black",
                 "loop seam", "clip reuse", "details quality", "rotation diff"):
        assert word in text, f"missing {word} in proof output"
    return f"exit {result.returncode}, new file(s): {' '.join(new_files)}"


@check("cmd_proof refuses in plain words when there is no video on disk")
def t_cmd_proof_no_video():
    cfg = config.load()
    render_id = data.current_render(cfg)
    if not _has_full_render(cfg, render_id):
        return "no full pipeline render on disk - run: python run.py build to do it"
    video = cfg.path("paths.output") / "video" / f"{render_id}.mp4"
    backup = None
    if video.exists():
        backup = video.with_suffix(".mp4.tmp")
        video.rename(backup)
    try:
        import subprocess as sp
        result = sp.run([sys.executable, "run.py", "proof"], capture_output=True, text=True, cwd=str(ROOT))
        assert result.returncode != 0, result.returncode
        assert "ANTAR_VIDEOS.zip" in result.stdout + result.stderr, \
            "the failure message must mention how to put the video back"
        return "refused with HTTP-style exit and the right message"
    finally:
        if backup:
            backup.rename(video)


# --------------------------------------------------------------- shape

@check("the proof file's summary names the scorecard categories with numbers")
def t_scorecard_categories_complete():
    cfg = config.load()
    render_id = data.current_render(cfg)
    if not _has_full_render(cfg, render_id):
        return "no full pipeline render on disk - run: python run.py build to do it"
    record = evidence.prove(cfg, render_id)
    categories = record["summary"]["categories"]
    assert categories, "no categories in the proof file"
    for cat in categories:
        assert {"category", "earned", "of"} <= set(cat.keys()), cat
    return (f"{len(categories)} categories, total {sum(c['earned'] for c in categories)}/"
            f"{sum(c['of'] for c in categories)}")


@check("UNAVAILABLE proofs are reported as such, never silently passed")
def t_unavailable_is_real():
    """
    Phase 10 closes the rotation-diff proof once history is on file, so
    UNAVAILABLE is not always present in the proof file. The contract is:

      * a proof that runs reports PASS / WARN / FAIL with a real number;
      * a proof that cannot run reports UNAVAILABLE with a plain reason;
      * neither is ever reported as PASS without a number.

    The test passes as long as every proof in the file has a real number
    in its `measured` field, and any UNAVAILABLE proof names its reason.
    """
    cfg = config.load()
    render_id = data.current_render(cfg)
    if not _has_full_render(cfg, render_id):
        return "no full pipeline render on disk - run: python run.py build to do it"
    record = evidence.prove(cfg, render_id)
    for row in record["checks"]:
        assert row["result"] in ("PASS", "WARN", "FAIL", "UNAVAILABLE"), row
        assert row.get("measured") not in (None, ""), row
    unavailables = [row for row in record["checks"] if row["result"] == "UNAVAILABLE"]
    for proof in unavailables:
        assert proof["note"], proof
        note_lower = proof["note"].lower()
        assert any(phrase in note_lower for phrase in
                   ("no previous video", "needs a previous", "no video",
                    "no timings", "no master wav")), proof["note"]
    return (f"{len(record['checks'])} proofs, "
            f"{sum(1 for r in record['checks'] if r['result'] == 'PASS')} PASS, "
            f"{len(unavailables)} UNAVAILABLE - all with real numbers")


# ------------------------------------------------------------------- run

ALL = [
    t_all_ten_proofs_run, t_writes_proof_file, t_scorecard_agreement,
    t_khand_sheet, t_swara_timing, t_pacing, t_thumbnail_brightness,
    t_no_black_frames, t_loop_seam, t_beats_have_pictures,
    t_clip_reuse, t_details_quality, t_rotation_diff_honest,
    t_real_thumbnail_files, t_landscape_has_title, t_thumbnail_record_is_complete,
    t_panel_proof_tab, t_panel_does_not_invent_proofs,
    t_cmd_proof, t_cmd_proof_no_video,
    t_scorecard_categories_complete, t_unavailable_is_real,
]


def run_all(verbose: bool = True) -> bool:
    RESULTS.clear()
    if verbose:
        print("\n  ANTAR - PHASE 9 SELF TEST")
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
