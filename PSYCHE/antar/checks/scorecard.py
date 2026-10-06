"""
ANTAR - the 100-point scorecard.

The master plan's own table, scored from measurements that already exist:

  Visibility     20   brightness, contrast, no black frames
  Hook           15   frame 1 triple redundancy, spoken start inside a second
  Structure      15   loop, peak at the end, micro-loops
  Picture        15   every beat's picture matches its words
  Language       10   तुम, conversational, no imperatives, no names
  Details        15   title score, description, tags
  Audio           5   voice, loudness, timing
  Distinctness    5   differs from the last 10

Upload unlock: 85.

Two rules about honesty here:

  * A category whose inputs do not exist yet - descriptions and tags (Phase 7),
    the last-ten history (Phase 10) - is WITHHELD, not scored as zero and not
    scored as full. The report says how many points could not be measured, and
    the unlock says it cannot be judged yet instead of faking a pass.
  * Every point that IS awarded has a measurement behind it, printed next to
    the category. A score with no number under it is a decoration.
"""

from __future__ import annotations

from .report import FAIL, PASS, UNAVAILABLE, WARN, Report

UNLOCK = 85


def _find(report: Report, name: str):
    for check in report.checks:
        if check.name == name:
            return check
    return None


def grade(config, bundle: dict, report: Report, *, sweep: list[dict],
          audio_stats: dict) -> dict:
    categories: list[dict] = []

    def category(name: str, of: int, earned: float, notes: list[str],
                 withheld: float = 0.0, why: str = "") -> None:
        entry = {"category": name, "of": of, "earned": round(earned, 1),
                 "notes": [n for n in notes if n]}
        if withheld:
            entry["withheld"] = round(withheld, 1)
            entry["why"] = why
        categories.append(entry)

    # ---------------------------------------------------------- Visibility 20
    tile = _find(report, "thumbnail brightness")
    darkest = _find(report, "darkest frame")
    visibility = 0.0
    notes: list[str] = []
    if tile and tile.status != UNAVAILABLE:
        inside = tile.status == PASS
        visibility += 8 if inside else max(0.0, 8 - abs(_tile_gap(tile)) * 0.8)
        notes.append("tile brightness " + ("in band" if inside else "outside the band"))
    contrast_ok = sweep and min(r["mean"] for r in sweep) >= 30
    if sweep:
        spread = max(r["mean"] for r in sweep) - min(r["mean"] for r in sweep)
        visibility += 6 if contrast_ok else 3
        notes.append(f"per-second spread {spread:.0f}/255, darkest {min(r['mean'] for r in sweep):.0f}")
    if darkest and darkest.status != UNAVAILABLE:
        visibility += 6 if darkest.status == PASS else 0
        notes.append("blackest frame " + ("inside the rule" if darkest.status == PASS
                                          else "over the rule"))
    category("Visibility", 20, visibility, notes)

    # ------------------------------------------------------------------ Hook 15
    hook = 0.0
    notes = []
    build = bundle.get("build") or {}
    popups = build.get("type") or []
    script = (bundle.get("script") or {}).get("script") or {}
    beats = script.get("beats") or []
    first_popup = (min(popups, key=lambda p: _start_of(p)) if popups else None)
    if first_popup and _start_of(first_popup) <= 0.12:
        hook += 4
        notes.append(f"a word is on screen at {_start_of(first_popup):.2f}s")
    if first_popup and beats:
        said = {w for w in _words(first_popup.get("text", ""))}
        spoken = {w for w in _words(beats[0].get("line_hi", ""))}
        if said and said <= spoken:
            hook += 4
            notes.append("the first words on screen are the first words spoken")
    shots = (bundle.get("plan") or {}).get("shots") or []
    if shots and (shots[0].get("kind") or "clip") == "clip":
        hook += 3
        notes.append("frame 1 is real footage, not a placeholder")
    audio_start = _find(report, "audio start")
    if audio_start and audio_start.status == PASS:
        hook += 4
        notes.append("the voice starts inside a second ("
                     + audio_start.measured + ")")
    category("Hook", 15, hook, notes)

    # ------------------------------------------------------------- Structure 15
    # The spec's line is "loop, peak at end, micro-loops". The loop is two
    # things in this project - the seam closes the file, the closing line
    # rhymes with the opening - so it gets two parts, and they are weighted
    # 4/4/4/3 = 15.
    structure = 0.0
    notes = []
    seam = _find(report, "loop seam")
    if seam and seam.status == PASS:
        structure += 4
        notes.append("loop seam closed (" + seam.measured + ")")
    ret = _find(report, "loop return")
    if ret and ret.status == PASS:
        structure += 4
        notes.append("the closing line rhymes with the opening (" + ret.measured + ")")
    peak = _find(report, "peak position")
    if peak and peak.status == PASS:
        structure += 4
        notes.append("the payoff lands in the last two seconds")
    else:
        notes.append("peak " + (peak.measured if peak else "not measured"))
    duration = _find(report, "duration")
    if duration is not None:
        notes.append("duration " + duration.measured
                     + ("" if duration.status == PASS else " (outside the target band)"))
    micro = _find(report, "micro-loop")
    if micro and micro.status == PASS:
        structure += 3
        notes.append("an open question inside every 15 seconds")
    else:
        notes.append("micro-loop " + (micro.measured if micro else "not measured"))
    category("Structure", 15, structure, notes)

    # --------------------------------------------------------------- Picture 15
    picture = 0.0
    notes = []
    if shots:
        covered = sum(1 for s in shots if s.get("path"))
        picture += 6 * (covered / len(shots))
        notes.append(f"{covered} of {len(shots)} beats have a picture")
        resolved = sum(1 for s in shots if (s.get("query") or s.get("object_hi")))
        picture += 5 * (resolved / len(shots))
        notes.append(f"{resolved} of {len(shots)} beats name a real object")
    faces = (bundle.get("build") or {}).get("checks") or []
    face_check = next((c for c in faces if "face" in c["check"]), None)
    withheld_faces = 0.0
    if face_check and face_check["pass"]:
        picture += 4
        notes.append(face_check["detail"])
    elif face_check and not face_check["pass"]:
        notes.append("faces: " + face_check["detail"])
    else:
        withheld_faces = 4.0
    category("Picture", 15, picture, notes, withheld=withheld_faces,
             why="the face scan did not run on this render")

    # -------------------------------------------------------------- Language 10
    language = 0.0
    notes = []
    whole = " ".join(b.get("line_hi", "") for b in beats)
    if "तुम" in whole:
        language += 4
        notes.append(f"तुम appears {whole.count('तुम')} times")
    if "आप" not in whole:
        language += 3
        notes.append("आप never appears")
    names = _find(report, "names present")
    if names and names.status == PASS:
        language += 3
        notes.append("no names")
    category("Language", 10, language, notes)

    # --------------------------------------------------------------- Details 15
    title = _find(report, "title score")
    details_earned = 0.0
    withheld_details = 0.0
    notes = []
    if title and title.status != UNAVAILABLE:
        title_points = 10 * min(1.0, _title_total(title) / 100.0)
        details_earned += title_points
        notes.append(f"title scored {title.measured}")
    else:
        withheld_details += 10
    has_details = bool(bundle.get("details"))
    if has_details:
        details_earned += 5
        notes.append("description and tags are on file")
    else:
        withheld_details += 5
        notes.append("description and tags do not exist yet (Phase 7)")
    category("Details", 15, details_earned, notes, withheld=withheld_details,
             why="the details generator arrives in Phase 7")

    # ----------------------------------------------------------------- Audio 5
    audio = 0.0
    notes = []
    loudness = _find(report, "loudness")
    if loudness and loudness.status == PASS:
        audio += 2
        notes.append(loudness.measured)
    if audio_start and audio_start.status == PASS:
        audio += 2
        notes.append("voice at " + audio_start.measured)
    marks = (bundle.get("audio") or {}).get("word_timings") or []
    if marks:
        audio += 1
        notes.append(f"{len(marks)} word timings measured")
    category("Audio", 5, audio, notes)

    # ----------------------------------------------------------- Distinctness 5
    rotation = _find(report, "rotation")
    if rotation and rotation.status != UNAVAILABLE and "first video" not in rotation.measured:
        distinct = 5.0 if rotation.status == PASS else 2.5
        category("Distinctness", 5, distinct, [rotation.measured])
    else:
        category("Distinctness", 5, 0.0, [],
                 withheld=5.0, why="no history to compare against until Phase 10")

    # ------------------------------------------------------------------- totals
    earned = sum(c["earned"] for c in categories)
    withheld = sum(c.get("withheld", 0) for c in categories)
    return {
        "categories": categories,
        "total": round(earned),
        "withheld": round(withheld),
        "measured_of": round(100 - withheld),
        "unlock": UNLOCK,
        "missing": [c["category"] for c in categories if c.get("withheld")],
    }


def _start_of(popup: dict) -> float:
    """When a popup starts. None means missing; 0.000s is a real time."""
    value = popup.get("start")
    try:
        return float(value)
    except (TypeError, ValueError):
        return 999.0


def _words(text: str) -> list[str]:
    from . import textscan

    return textscan.words(text)


def _tile_gap(check) -> float:
    import re

    numbers = [float(n) for n in re.findall(r"(\d+\.?\d*)", check.measured)]
    if not numbers:
        return 0.0
    worst = min(numbers[:3]) if len(numbers) >= 3 else numbers[0]
    if worst < 35:
        return 35 - worst
    return max(0.0, worst - 45)


def _title_total(check) -> float:
    import re

    match = re.search(r"(\d+)/100", check.measured)
    return float(match.group(1)) if match else 0.0
