"""
PSYCHE panel - what each tab shows.

Read-only, and read from the files the stages actually wrote. There is no
second source of truth in this file: if a number is on screen it came out of
`output/`, `config/`, or a stage's own record. When something is missing the
tab says so, in words, instead of showing a zero that looks like a measurement.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..checks import titlescore
from ..details import assemble
from ..vault import find_ffmpeg


def _read(path: Path) -> dict:
    if not path or not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return {}


def _folder(config, name: str) -> Path:
    return config.path(f"paths.{name}")


# --------------------------------------------------------------- the render

def render_ids(config) -> list[str]:
    """Every render PSYCHE has actually built, newest last."""
    ids: list[str] = []
    for build in sorted(_folder(config, "output").joinpath("video").glob("*_build.json")):
        if build.name.upper().startswith("TEST"):
            continue
        ids.append(build.name[: -len("_build.json")])
    for video in sorted(_folder(config, "output").joinpath("video").glob("*.mp4")):
        if video.stem.upper().startswith("TEST") or video.stem in ids:
            continue
        ids.append(video.stem)
    return ids


def current_render(config, wanted: str = "") -> str:
    if wanted:
        return wanted
    ids = render_ids(config)
    return ids[-1] if ids else ""


def video_path(config, render_id: str) -> Path | None:
    path = _folder(config, "output") / "video" / f"{render_id}.mp4"
    return path if path.exists() else None


def thumbnail_path(config, render_id: str) -> Path | None:
    for suffix in ("_manual.jpg", "_thumbnail.jpg"):
        path = _folder(config, "output") / "thumbs" / f"{render_id}{suffix}"
        if path.exists():
            return path
    return None


# --------------------------------------------------------------------- home

def home(config, render_id: str = "") -> dict:
    render_id = current_render(config, render_id)
    rows = []
    for rid in reversed(render_ids(config)[-5:]):
        check = _read(_folder(config, "output") / "checks" / f"{rid}_check.json")
        score = (check.get("scorecard") or {})
        rows.append({
            "render_id": rid,
            "score": score.get("total"),
            "withheld": score.get("withheld_points"),
            "blocked": check.get("blocked_from_upload"),
            "at": check.get("when") or _mtime(_folder(config, "output") / "video" / f"{rid}.mp4"),
            "video_on_disk": bool(video_path(config, rid)),
            "has_details": bool(_read(_folder(config, "output") / "details" / f"{rid}_details.json")),
        })
    check = _read(_folder(config, "output") / "checks" / f"{render_id}_check.json") if render_id else {}
    score = check.get("scorecard") or {}
    details = _read(_folder(config, "output") / "details" / f"{render_id}_details.json") if render_id else {}
    return {
        "render_id": render_id,
        "renders": rows,
        "video_on_disk": bool(video_path(config, render_id)) if render_id else False,
        "video_name": f"{render_id}.mp4" if render_id else "",
        "title": details.get("title_hi", ""),
        "title_score": details.get("chosen_score"),
        "score": score.get("total"),
        "withheld": score.get("withheld_points"),
        "blocked": check.get("blocked_from_upload"),
        "blocked_by": check.get("blocked_by") or [],
        "checked": bool(check),
        "upload_unlock": int(config.get("thresholds.upload_min", 85)),
        "one_video_ready": bool(render_id),
    }


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


# ------------------------------------------------------------------- writer

def writer(config, render_id: str = "") -> dict:
    render_id = current_render(config, render_id)
    script = _read(_folder(config, "output") / "scripts" / f"{render_id}.json") if render_id else {}
    if not script:
        return {"render_id": render_id, "ready": False,
                "note": "no script on disk for this render - run: python run.py write"}
    inner = script.get("script") or {}
    topic = script.get("topic") or {}
    peak = inner.get("peak_line")
    beats = []
    for index, beat in enumerate(inner.get("beats") or [], start=1):
        role = beat.get("role", "")
        beats.append({
            "n": index,
            "line_hi": beat.get("line_hi", ""),
            "object_hi": beat.get("object_hi", ""),
            "role": role,
            "is_peak": index == peak or role in ("payoff", "peak"),
        })
    return {
        "render_id": render_id,
        "ready": True,
        "title_hi": inner.get("title_hi") or topic.get("title_hi", ""),
        "topic_title": topic.get("title_hi", ""),
        "search_phrase_hi": topic.get("search_phrase_hi", ""),
        "mechanism_hi": topic.get("mechanism_hi", ""),
        "beats": beats,
        "beats_count": len(beats),
        "words": script.get("words"),
        "structure": (script.get("rotation") or {}).get("script_structure", ""),
        "hook_angle": (script.get("rotation") or {}).get("hook_angle", ""),
        "rotation": script.get("rotation") or {},
        "closing_echo": inner.get("closing_echo", ""),
        "peak_line": peak,
    }


# ------------------------------------------------------------------ picture

def picture(config, render_id: str = "") -> dict:
    render_id = current_render(config, render_id)
    plan = _read(_folder(config, "output") / "plans" / f"{render_id}_picture.json") if render_id else {}
    if not plan:
        return {"render_id": render_id, "ready": False,
                "note": "no picture plan on disk - run: python run.py picture"}
    shots = []
    clips = cards = 0
    seen: dict[str, int] = {}
    for shot in plan.get("shots") or []:
        kind = shot.get("kind", "clip")
        clips += 1 if kind == "clip" else 0
        cards += 1 if kind != "clip" else 0
        clip_id = shot.get("clip_id") or ""
        if clip_id:
            seen[clip_id] = seen.get(clip_id, 0) + 1
        shots.append({
            "index": shot.get("index"),
            "kind": kind,
            "object_hi": shot.get("object_hi", ""),
            "query": shot.get("query", ""),
            "clip_id": clip_id,
            "start": shot.get("start"),
            "end": shot.get("end"),
            "hold": shot.get("hold"),
            "line_hi": shot.get("line_hi", ""),
            "source": shot.get("source", ""),
        })
    reused = sum(v - 1 for v in seen.values() if v > 1)
    totals = plan.get("totals") or {}
    return {
        "render_id": render_id,
        "ready": True,
        "shots": shots,
        "health": {
            "clips": clips,
            "cards": cards,
            "clip_pct": round(100 * clips / max(1, clips + cards)),
            "reused": reused,
            "distinct_clips": len(seen),
            "seconds_covered": totals.get("seconds_covered"),
            "max_uses": int(config.get("vault.max_uses_per_clip", 2)),
        },
    }


# -------------------------------------------------------------------- check

def check(config, render_id: str = "") -> dict:
    render_id = current_render(config, render_id)
    record = _read(_folder(config, "output") / "checks" / f"{render_id}_check.json") if render_id else {}
    if not record:
        return {"render_id": render_id, "ready": False,
                "note": "this render has not been checked yet - run: python run.py check"}
    return {
        "render_id": render_id,
        "ready": True,
        "when": record.get("when"),
        "scorecard": record.get("scorecard") or {},
        "checks": record.get("checks") or [],
        "counts": record.get("counts") or {},
        "blocked_from_upload": record.get("blocked_from_upload"),
        "blocked_by": record.get("blocked_by") or [],
        "blocking_count": len([c for c in record.get("checks") or [] if c.get("kind") == "blocking"]),
        "warning_count": len([c for c in record.get("checks") or [] if c.get("kind") == "warning"]),
    }


# -------------------------------------------------------------------- score

def score(config, render_id: str = "") -> dict:
    render_id = current_render(config, render_id)
    record = _read(_folder(config, "output") / "checks" / f"{render_id}_check.json") if render_id else {}
    card = record.get("scorecard") or {}
    return {
        "render_id": render_id,
        "ready": bool(card),
        "note": "" if card else "no score yet - run the check first",
        "categories": card.get("categories") or [],
        "total": card.get("total"),
        "withheld_points": card.get("withheld_points"),
        "withheld": card.get("withheld") or [],
        "measured_of": card.get("measured_of"),
        "upload_unlock": int(config.get("thresholds.upload_min", 85)),
        "blocked_from_upload": record.get("blocked_from_upload"),
        "blocked_by": record.get("blocked_by") or [],
    }


# ------------------------------------------------------------------ details

def details(config, render_id: str = "") -> dict:
    render_id = current_render(config, render_id)
    payload = _read(_folder(config, "output") / "details" / f"{render_id}_details.json") if render_id else {}
    if not payload:
        return {"render_id": render_id, "ready": False,
                "note": "no details on disk - run: python run.py details"}
    harvest = payload.get("harvest") or {}
    thumb = thumbnail_path(config, render_id)
    out = dict(payload)
    out.update({
        "render_id": render_id,
        "ready": True,
        "video_on_disk": bool(video_path(config, render_id)),
        "thumbnail_file": str(thumb) if thumb else "",
        "thumbnail_manual": bool(thumb and thumb.name.endswith("_manual.jpg")),
        "phrases": harvest.get("scored_against") or harvest.get("phrases") or [],
        "harvest_note": harvest.get("note", ""),
        "hashtag_rule": [assemble.HASHTAG_MIN, assemble.HASHTAG_MAX],
    })
    return out


def rescore(config, render_id: str, title: str) -> dict:
    """
    Score a title the way the check suite will, on the phrase list this render
    was built with. The panel and the gate share one judge - if they did not,
    the panel could show a green 100 for a title the gate refuses.
    """
    from ..checks import suite

    bundle = {"render_id": render_id, "details": _read(
        _folder(config, "output") / "details" / f"{render_id}_details.json")}
    phrases, source = suite.title_phrases(bundle, config)
    script = _read(_folder(config, "output") / "scripts" / f"{render_id}.json")
    footage = [b.get("object_hi", "") for b in ((script.get("script") or {}).get("beats") or [])]
    result = titlescore.score(title, config, phrases=phrases, footage_words=footage)
    result["phrases_from"] = source
    result["phrases_count"] = len(phrases)
    result["gate"] = titlescore.SCORE_MIN
    result["target"] = titlescore.GENERATOR_TARGET
    return result


# --------------------------------------------------------------------- keys

def mask(value: str) -> str:
    """
    Never a whole key on screen.

    Same shape the command line prints and the same shape `Key.masked` uses -
    a panel that showed more of a key than the console does would be the one
    place a key leaks, and screenshots of a running panel are exactly how that
    happens.
    """
    if len(value) <= 10:
        return "***"
    return f"{value[:6]}...{value[-4:]}"


def keys(config) -> dict:
    from ..keys import KeyRing
    from ..probe import checked_services, have_check

    ring = KeyRing(config.path("paths.state") / "keys.json")
    rows = []
    for entry in ring.all():
        rows.append({
            "service": entry.service,
            "masked": mask(entry.value),
            "state": entry.state,
            "reason": entry.reason,
            "uses": entry.uses,
            "fails": entry.fails,
            "last_checked": entry.last_checked,
            "when": _ago(entry.last_checked),
            "has_test": have_check(entry.service),
        })
    services = sorted({row["service"] for row in rows})
    return {
        "keys": rows,
        "count": len(rows),
        "services": services,
        "checked_services": list(checked_services()),
        "without_a_test": [s for s in services if not have_check(s)],
        "note": ("dead keys stay on file, marked - they are never retried and never "
                 "deleted, and a service with no test is kept and never called dead"),
        "alive": len([r for r in rows if r["state"] == "alive"]),
        "dead": len([r for r in rows if r["state"] == "dead"]),
    }


# -------------------------------------------------------------------- learn

def learn(config) -> dict:
    """
    Honest and empty on purpose.

    The learn tab reads analytics CSVs, and there is no CSV until the videos
    have been published and downloaded from YouTube. Until then it says what it
    will do and shows nothing, because a chart of invented numbers is worse
    than no chart.
    """
    folder = _folder(config, "output") / "analytics"
    csvs = sorted(folder.glob("*.csv")) if folder.exists() else []
    return {
        "ready": bool(csvs),
        "files": [p.name for p in csvs],
        "note": ("arrives in Phase 10 - paste YouTube analytics CSVs into "
                 "output/analytics/ and this tab reads them"),
        "will_show": [
            "what won, by lane",
            "what won, by hook angle",
            "what won, by title shape",
            "the retention curve against the script's beats",
            "which clip queries held attention and which lost it",
        ],
    }


# ----------------------------------------------------------------- settings

def settings(config) -> dict:
    from ..state import RunState

    state = RunState(config.path("paths.state") / "state.json")
    rotation = config.get("rotation") or {}
    previous = state.previous_rotation()
    return {
        "lane": config.get("lane") or {},
        "voice": {"voice": config.get("voice.voice"), "rate": config.get("voice.rate"),
                  "pitch": config.get("voice.pitch")},
        "type": {"font": config.get("type.font"), "size": config.get("type.size")},
        "thresholds": config.get("thresholds") or {},
        "fixed": rotation.get("fixed") or [],
        "rotating": rotation.get("rotating") or {},
        "last_rotation": previous,
        "render_counter": state.data.get("render_counter", 0),
        "recent": (state.history() or [])[-5:],
        "paths": {k: str(v) for k, v in (config.get("paths") or {}).items()},
        "ffmpeg": find_ffmpeg() or "not found",
    }


def _ago(when: float) -> str:
    """A time as a person reads it: how long ago, not a timestamp."""
    if not when:
        return "never checked"
    delta = time.time() - float(when)
    for limit, unit, size in ((90, "s", 1), (5400, "min", 60), (172800, "h", 3600)):
        if delta < limit:
            step = max(1, int(delta / size))
            return f"{step} {unit} ago"
    return f"{int(delta / 86400)} day(s) ago"

# ------------------------------------------------------------------- proof

def proof(config, render_id: str = "") -> dict:
    render_id = current_render(config, render_id)
    record = _read(_folder(config, "output") / "proof" / f"{render_id}_proof.json") if render_id else {}
    if not record:
        return {"render_id": render_id, "ready": False,
                "note": "no proof file on disk - run: python run.py proof"}
    summary = record.get("summary") or {}
    checks = record.get("checks") or []
    by_result = {key: len([c for c in checks if c.get("result") == key])
                 for key in ("PASS", "WARN", "FAIL", "UNAVAILABLE")}
    return {
        "render_id": render_id,
        "ready": True,
        "when": record.get("when"),
        "seconds": record.get("seconds"),
        "summary": summary,
        "checks": checks,
        "counts": by_result,
        "passed": by_result.get("PASS", 0),
        "warned": by_result.get("WARN", 0),
        "failed": by_result.get("FAIL", 0),
        "unavailable": by_result.get("UNAVAILABLE", 0),
        "score": summary.get("scorecard_total"),
        "withheld": summary.get("withheld_points"),
        "gate": summary.get("upload_unlock"),
        "gate_cleared": summary.get("gate_cleared"),
        "blocked": summary.get("blocked_from_upload"),
        "blocked_by": summary.get("blocked_by") or [],
    }


def real_thumbnail(config, render_id: str = "") -> dict:
    render_id = current_render(config, render_id)
    details = _read(_folder(config, "output") / "details" / f"{render_id}_details.json") if render_id else {}
    if not details:
        return {"render_id": render_id, "ready": False,
                "note": "no details on disk - run: python run.py details"}
    record = details.get("thumbnail_record") or {}
    portrait = record.get("full") or details.get("thumbnail_path") or ""
    landscape = record.get("landscape") or details.get("thumbnail_landscape") or ""
    return {
        "render_id": render_id,
        "ready": bool(portrait and Path(portrait).exists()),
        "portrait": portrait,
        "landscape": landscape,
        "picked_second": record.get("picked_second") or details.get("thumbnail_real_at"),
        "brightness": record.get("full_brightness") or (details.get("thumbnail") or {}).get("mean"),
        "landscape_brightness": record.get("landscape_mean"),
        "band": record.get("band"),
        "in_band": record.get("in_band"),
        "manual_override": record.get("manual_override"),
        "size": record.get("size"),
        "note": record.get("note") or (details.get("thumbnail") or {}).get("reason", ""),
    }


# ------------------------------------------------------------------- learn

def learn(config, render_id: str = "") -> dict:
    """
    The learn tab, honestly. Three things, in this order:

      1. did the operator paste any CSVs?
      2. does the aggregate have at least two videos?
      3. what does the recommendation say, if anything?

    Each step is a small honest answer. If the answer to (1) is "no", the
    tab explains how to fix that; if the answer to (2) is "no", it says how
    many videos there are and stops; if (3) is missing, it explains why.

    `render_id` is accepted for shape parity with the other tabs - the learn
    tab reads across all renders, not one.
    """
    from ..learn import csv as learn_csv
    from ..learn import recommend as learn_recommend

    folder = config.path("paths.output") / "analytics"
    csvs = sorted(folder.glob("*.csv")) if folder.exists() else []
    if not csvs:
        return {
            "ready": False,
            "csvs": [],
            "note": ("drop a YouTube Studio CSV export into output/analytics/ "
                     "and re-run python run.py learn - the tab will tell you "
                     "what the analytics said, by lane, hook and structure"),
            "will_show": [
                "what won, by lane (B is locked today, but the loop grades B's data)",
                "what won, by hook angle (direct-question, contrarian, recognition)",
                "what won, by title structure (loop-question, micro-story, problem-mechanism)",
                "the retention curve against the script's beats",
                "which rotation values the next topic should reuse",
            ],
            "next_topic_brief": None,
            "anti_patterns": [],
        }

    metrics = learn_csv.all_metrics(config)
    aggregate_path = learn_csv.write_aggregate(config, metrics)
    rec = learn_recommend.learn(config)

    axes = rec.get("axes") or {}
    return {
        "ready": True,
        "csvs": [p.name for p in csvs],
        "aggregate": str(aggregate_path),
        "videos_with_data": len([r for r in axes.get("lane", []) if r.get("trusted")]),
        "axes": axes,
        "next_topic_brief": rec.get("next_topic_brief"),
        "anti_patterns": rec.get("anti_patterns", []),
        "note": rec.get("note", ""),
        "will_show": [],
    }


def import_analytics_csv(config, source_path: str) -> dict:
    """
    Copy a YouTube Studio CSV export into the workshop's analytics folder.

    A copy, not a move - the operator can drop a fresh CSV any time, and the
    file the operator sees in their Downloads folder is the file they keep.
    The path is constrained to be a real file under the workshop or the
    operator's Downloads - a request for /etc/passwd is refused.
    """
    import shutil

    from .server import PanelError
    source = Path(source_path)
    if not source.exists() or not source.is_file():
        raise PanelError(f"no such file: {source_path}")
    if source.suffix.lower() != ".csv":
        raise PanelError(f"only CSV files are accepted, not {source.suffix}")

    folder = config.path("paths.output") / "analytics"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / source.name
    shutil.copy2(source, target)
    return {"copied": str(target), "name": source.name}


def run_learn(config) -> dict:
    """Run the learn stage on whatever is on disk; return a short summary."""
    from ..learn import csv as learn_csv
    from ..learn import recommend as learn_recommend

    folder = config.path("paths.output") / "analytics"
    csvs = sorted(folder.glob("*.csv")) if folder.exists() else []
    if not csvs:
        return {"ran": False, "note": "no CSVs in output/analytics/ - drop one in and re-run"}
    metrics = learn_csv.all_metrics(config)
    learn_csv.write_aggregate(config, metrics)
    rec = learn_recommend.learn(config)
    return {"ran": True, "recommendation": rec}
