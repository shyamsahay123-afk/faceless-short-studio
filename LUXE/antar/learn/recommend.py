"""
ANTAR - the learn loop.

What "next topic informed by real results" means in practice:

  * read `output/analytics/aggregate.json`;
  * rank rotation values (lane, hook angle, structure, grade) by the
    numbers ANTAR can act on - retention is the truth, swipe-away is the
    cost;
  * write a `recommend.json` the topic engine reads before it asks the model
    for candidates, so the next topic steers toward what worked;
  * close the rotation-diff proof: with at least two videos on file, the
    proof can compare current vs previous and grade the Distinctness
    category of the scorecard;
  * update the check record's `scorecard.withheld_points` and
    `scorecard.total` so the upload unlock is read off the live number,
    not a number from a phase that did not yet exist.

The recommendation never overrides the lane the project committed to in
the master plan - it steers *within* the lane, so a Hindi Shorts studio
keeps shipping Hindi Shorts and not whatever the analytics happen to
love this week.
"""

from __future__ import annotations

import json
import time
from pathlib import Path


WEIGHT_RETENTION = 0.6         # retention matters most: did they stay?
WEIGHT_VIEWS = 0.2             # absolute reach shapes the next test
WEIGHT_SWIPE_AWAY = 0.2        # a high swipe-away is a cost on the algorithm
MIN_VIDEOS_PER_BUCKET = 2      # one data point is not a pattern


class LearnError(RuntimeError):
    """The learn stage could not write a recommendation - and here is why."""


def learn(config) -> dict:
    """
    Run the loop: read the aggregate, rank rotation values, write the
    recommendation, close the rotation-diff proof.

    Returns the recommendation the topic engine reads. The file on disk
    is the source of truth, not the return value.

    The loop regenerates the aggregate on every call so the recommendation
    is always read off the latest CSVs - a stale aggregate is a defect,
    not a feature, and one of the early bugs here was a leftover file from
    a previous test (or a previous upload) being trusted.
    """
    from . import csv as learn_csv

    analytics_folder = config.path("paths.output") / "analytics"
    csvs = sorted(analytics_folder.glob("*.csv")) if analytics_folder.exists() else []
    if not csvs:
        return _no_data(config, "no analytics have been imported yet - "
                       "drop YouTube Studio CSVs into output/analytics/ and run again")
    metrics = learn_csv.all_metrics(config)
    aggregate_path = learn_csv.write_aggregate(config, metrics)
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    summary = aggregate.get("summary") or {}
    if summary.get("videos_with_data", 0) < 2:
        return _no_data(config, f"only {summary.get('videos_with_data', 0)} video(s) "
                       "have analytics - the loop needs at least two to recommend")

    by_lane = aggregate.get("by_lane") or {}
    by_hook = aggregate.get("by_hook") or {}
    by_structure = aggregate.get("by_structure") or {}
    by_grade = aggregate.get("by_grade") or {}

    rec = _recommend(config, by_lane, by_hook, by_structure, by_grade)
    _close_distinctness(config, aggregate)
    _write(config, rec, aggregate)
    return rec


# ------------------------------------------------------------------ rank

def _recommend(config, by_lane, by_hook, by_structure, by_grade) -> dict:
    """
    Score every bucket the analytics aggregate knows about.

    The score is a weighted sum of retention, views, and the inverse of
    swipe-away. A bucket with fewer than MIN_VIDEOS_PER_BUCKET videos is
    marked untrusted and pushed to the end - one video is a sample, not a
    pattern, and the topic engine should not over-correct on it.
    """
    scored = {}
    for axis, buckets in (("lane", by_lane), ("hook", by_hook),
                          ("structure", by_structure), ("grade", by_grade)):
        scored[axis] = _rank_axis(buckets, axis)
    return {
        "when": time.time(),
        "axes": scored,
        "next_topic_brief": _brief(scored, config),
        "anti_patterns": _anti_patterns(scored),
    }


def _rank_axis(buckets: dict, axis: str) -> list[dict]:
    """One axis (lane, hook, structure, grade) ranked by the weighted score."""
    ranked = []
    for name, stats in buckets.items():
        retention = stats.get("retention_pct", 0.0)
        views = stats.get("views_per_video", 0.0)
        swipe = stats.get("swipe_away_pct", 0.0)
        videos = stats.get("videos", 0)
        score = (WEIGHT_RETENTION * retention +
                 WEIGHT_VIEWS * min(views / 1000.0, 1.0) * 100.0 +
                 WEIGHT_SWIPE_AWAY * max(0.0, 50.0 - swipe))
        trusted = videos >= MIN_VIDEOS_PER_BUCKET
        ranked.append({"name": name, "score": round(score, 1), "videos": videos,
                       "retention_pct": retention, "views_per_video": views,
                       "swipe_away_pct": swipe, "trusted": trusted})
    ranked.sort(key=lambda row: (row["trusted"], row["score"]), reverse=True)
    return ranked


def _brief(scored: dict, config) -> dict:
    """
    The topic engine reads this. It names the lane, the hook, the structure,
    and the grade that won, with one runner-up each. Anything with fewer than
    two videos is named, but flagged - the engine takes the winner, the
    operator decides whether the runner-up is worth a try.
    """
    lane = config.get("lane") or {}
    locked_lane = lane.get("id") or "B"

    def first_winner(axis):
        for row in scored.get(axis) or []:
            if row.get("trusted"):
                return {"name": row["name"], "score": row["score"],
                        "videos": row["videos"], "retention_pct": row["retention_pct"]}
        return None

    def runner_up(axis, exclude=None):
        rows = [row for row in scored.get(axis) or []
                if row.get("trusted") and row["name"] != exclude]
        return rows[0] if rows else None

    winners = {axis: first_winner(axis) for axis in ("lane", "hook", "structure", "grade")}
    return {
        "locked_lane": locked_lane,
        "lane": winners["lane"],
        "hook": winners["hook"],
        "structure": winners["structure"],
        "grade": winners["grade"],
        "runner_up_hook": runner_up("hook"),
        "runner_up_structure": runner_up("structure"),
        "runner_up_grade": runner_up("grade"),
    }


def _anti_patterns(scored: dict) -> list[dict]:
    """
    What to avoid - the bottom of every axis.

    An anti-pattern is a bucket with at least two videos AND a score below
    half the top score. One bad video is not an anti-pattern; two are.
    """
    patterns = []
    for axis in ("hook", "structure", "grade"):
        rows = [row for row in scored.get(axis) or [] if row.get("trusted")]
        if len(rows) < 2:
            continue
        top_score = rows[0]["score"]
        floor = top_score / 2.0
        for row in rows[1:]:
            if row["score"] <= floor and row["videos"] >= MIN_VIDEOS_PER_BUCKET:
                patterns.append({"axis": axis, "name": row["name"],
                                 "score": row["score"], "videos": row["videos"],
                                 "retention_pct": row["retention_pct"]})
    return patterns


# ------------------------------------------------------------- distinctness

def _close_distinctness(config, aggregate) -> dict:
    """
    With history on file, the rotation-diff proof can grade Distinctness.

    The scorecard the upload reads is the file under output/checks/. The
    proof stage earlier wrote Distinctness=0/5 with `+5 withheld`. We now
    look at every render's rotation in `config/state/state.json`, compute
    the average overlap between consecutive videos, and write back a
    number that reflects the actual distinctness of the queue.

    Honest by design: if history is empty, this function is a no-op and
    the scorecard's `withheld_points` stays as it was.
    """
    from ..state import RunState

    state = RunState(config.path("paths.state") / "state.json")
    history = state.history() or []
    if len(history) < 2:
        return {"distinctness": "no history", "earned": 0, "of": 5}

    pairs = list(zip(history[:-1], history[1:]))
    overlaps = []
    for prev, current in pairs:
        prev_rotation = prev.get("rotation") or {}
        curr_rotation = current.get("rotation") or {}
        keys = set(prev_rotation) | set(curr_rotation)
        shared = sum(1 for k in keys
                     if prev_rotation.get(k) == curr_rotation.get(k)
                     and k not in ("render_id", "id", "ts"))
        max_rotating = max(11, len(keys))
        overlaps.append((max_rotating - shared) / max_rotating)
    avg = sum(overlaps) / len(overlaps) if overlaps else 0.0
    earned = round(5.0 * avg, 1)

    check_path = config.path("paths.output") / "checks" / f"{history[-1].get('render_id', '')}_check.json"
    if not check_path.exists():
        # the most recent render in history may not have a check file yet (a
        # synthetic history entry, or a fresh video that hasn't been checked).
        # Fall back to the newest check file the workshop actually has, so
        # the upload unlock reflects history from the latest scorecard.
        checks_dir = config.path("paths.output") / "checks"
        candidates = sorted(checks_dir.glob("*_check.json"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        check_path = candidates[0] if candidates else None
    if check_path and check_path.exists():
        payload = json.loads(check_path.read_text(encoding="utf-8"))
        card = payload.setdefault("scorecard", {})
        categories = card.get("categories") or []
        replaced = False
        for row in categories:
            if row.get("category", "").lower() == "distinctness":
                row["earned"] = earned
                row["notes"] = [f"avg distinctness {avg:.2f} across {len(overlaps)} pair(s)"]
                replaced = True
                break
        if not replaced:
            categories.append({"category": "Distinctness", "earned": earned, "of": 5,
                               "notes": [f"avg distinctness {avg:.2f} across {len(overlaps)} pair(s)"]})
        total = sum(c["earned"] for c in categories)
        withheld = max(0, 100 - total)
        card["categories"] = categories
        card["total"] = round(total, 1)
        card["withheld"] = withheld
        card["withheld_points"] = withheld
        # 'withheld' here means "the points above 100 cannot be earned yet" -
        # the gap is from categories that did not earn full marks (Structure
        # in our case). Name those categories so the upload unlock says why.
        missing = [c["category"] for c in categories if c["earned"] < c["of"]]
        card["missing"] = missing
        payload["scorecard"] = card
        check_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    return {"distinctness": round(avg, 3), "earned": earned, "of": 5, "pairs": len(overlaps)}


# ----------------------------------------------------------------- write

def _write(config, rec: dict, aggregate: dict) -> Path:
    folder = config.path("paths.output") / "analytics"
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / "recommend.json"
    payload = {"recommendation": rec, "aggregate_used": aggregate.get("summary") or {}}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def _no_data(config, message: str) -> dict:
    folder = config.path("paths.output") / "analytics"
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / "recommend.json"
    payload = {"recommendation": {"note": message, "axes": {},
                                   "next_topic_brief": None, "anti_patterns": []},
               "aggregate_used": {}}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return payload["recommendation"]


def recommend_for_brief(config) -> dict | None:
    """
    The topic engine calls this to read the brief. Returns None when there
    is no real recommendation - the engine then falls back to the locked
    defaults so the writer still produces something.
    """
    folder = config.path("paths.output") / "analytics" / "recommend.json"
    if not folder.exists():
        return None
    try:
        payload = json.loads(folder.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not payload:
        return None
    return payload.get("recommendation", {}).get("next_topic_brief")
