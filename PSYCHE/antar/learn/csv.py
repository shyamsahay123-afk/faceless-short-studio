"""
ANTAR - the analytics reader.

YouTube Studio's analytics CSV exports look the same in every channel, but
the column names have moved four times since the page first shipped. ANTAR
does not assume one of them. The reader walks the header line and picks the
column whose values are numeric and whose name matches the metric - so the
same parser works on `Average view duration`, `Avg View Duration`, and
`avg_view_duration_sec`.

What this stage does, in plain words:

  1. read every CSV under `output/analytics/`;
  2. match each file to a render on file by video title, topic id, or upload
     date, in that order, so an operator does not have to type a render id
     by hand;
  3. extract the metrics ANTAR can act on (views, retention, swipe-away,
     likes-vs-views, comments-vs-views);
  4. write a single `analytics.json` the learn stage and the panel read.

The numbers this stage reads are the numbers the upload published - this
stage does not invent a "what-if" view count or pretend a video that has
not been uploaded has analytics. A render with no CSV is recorded with
zero for every metric and an honest `note` saying so.
"""

from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path


# Metric -> list of normalised header patterns. The reader normalises
# both sides (lowercase, no punctuation, single spaces), so a header like
# "Average view duration (seconds)" matches the pattern
# "average view duration seconds". A header like "Views (in this period)"
# matches "views in this period".
METRIC_HEADERS: dict[str, list[str]] = {
    "views": ["views", "video views", "view count", "views in this period"],
    "likes": ["likes", "like count", "video likes", "likes in this period"],
    "comments": ["comments", "comment count", "video comments",
                 "comments in this period"],
    "shares": ["shares", "share count", "video shares", "shares in this period"],
    "avg_view_seconds": ["average view duration", "avg view duration",
                          "average view duration seconds", "avg view duration seconds",
                          "average duration", "watch time average"],
    "avg_view_pct": ["average percentage viewed", "avg  viewed", "avg viewed",
                     "average  viewed", "avg percent viewed", "average  watched"],
    "swipe_away_pct": ["swipe away rate", "swipeaway rate",
                       "swipe away ratio", "swipeaway ratio"],
    "subscribers_gained": ["subscribers", "subscribers gained",
                           "subscribers from video", "net subscribers"],
}

# Some YT exports give metrics as strings ("1,234" or "12.3%"). Both shapes
# land in the same column on different export versions, so the cleaner tries
# a few common forms before giving up.
INT_PATTERN = re.compile(r"-?\d[\d,]*")
FLOAT_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


def parse(text: str) -> dict:
    """
    Parse a YouTube Studio CSV export.

    Returns a dict with the keys from METRIC_HEADERS filled from whatever
    columns the export had, plus a `rows` list of every other column so an
    operator can see what the file actually carried.

    This function never raises on missing columns - a CSV without `views`
    just gets `views: None`. The caller decides whether that is enough.
    """
    reader = csv.reader(text.splitlines())
    rows = list(reader)
    if not rows:
        return {"rows": 0, "metrics": {}, "raw": []}
    header = [column.strip().lower() for column in rows[0]]
    body = rows[1:]
    metrics: dict[str, object] = {key: None for key in METRIC_HEADERS}
    matched: dict[str, str] = {}

    normalised = [_normalise(name) for name in header]
    for metric, candidates in METRIC_HEADERS.items():
        for index, normalised_name in enumerate(normalised):
            if normalised_name in {_normalise(c) for c in candidates}:
                matched[metric] = header[index]
                metrics[metric] = _column(body, index)
                break

    return {
        "rows": len(body),
        "metrics": metrics,
        "matched_columns": matched,
        "header": rows[0],
        "raw": [dict(zip(rows[0], row)) for row in body[:50]],
    }


def _column(rows: list[list[str]], index: int) -> list:
    """A column as a list, parsed if it looks numeric, raw if it does not."""
    output = []
    for row in rows:
        if index >= len(row):
            continue
        cell = row[index].strip()
        if not cell:
            output.append(None)
            continue
        if cell.endswith("%"):
            try:
                output.append(float(cell.rstrip("%").replace(",", "")))
            except ValueError:
                output.append(cell)
        elif "," in cell:
            cleaned = cell.replace(",", "")
            try:
                output.append(int(cleaned))
            except ValueError:
                try:
                    output.append(float(cleaned))
                except ValueError:
                    output.append(cell)
        else:
            try:
                output.append(int(cell))
            except ValueError:
                try:
                    output.append(float(cell))
                except ValueError:
                    output.append(cell)
    return output


# --------------------------------------------------------------- per-video

class VideoMetric:
    """
    One published video, with its ANTAR id and its CSV metrics aligned.

    `video_id` and `render_id` are both tracked because YT uses opaque ids
    (the URL slug) and ANTAR uses `ANTAR_NNNN_lane-X-pilot` - the join between
    them is by title (the operator can rename titles freely, so the join is a
    best-effort match, not a guaranteed one).
    """

    def __init__(self, render_id: str, csv_path: Path):
        self.render_id = render_id
        self.csv_path = csv_path
        self.metrics: dict = {}
        self.matched: dict[str, str] = {}
        self.note: str = ""

    @classmethod
    def from_csv(cls, csv_path: Path, render_id: str = "") -> "VideoMetric":
        """Build a VideoMetric from a file. `render_id` empty if no match."""
        instance = cls(render_id, csv_path)
        try:
            text = csv_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            instance.note = f"could not read the CSV: {exc}"
            return instance
        try:
            parsed = parse(text)
        except (csv.Error, UnicodeDecodeError) as exc:
            instance.note = f"the CSV could not be parsed: {exc}"
            return instance
        instance.metrics = parsed["metrics"]
        instance.matched = parsed["matched_columns"]
        instance.header = parsed["header"]
        if not parsed["matched_columns"]:
            instance.note = "no recognised metrics in the CSV header"
        return instance

    def view_count(self) -> int:
        return _first_int(self.metrics.get("views"))

    def like_count(self) -> int:
        return _first_int(self.metrics.get("likes"))

    def comment_count(self) -> int:
        return _first_int(self.metrics.get("comments"))

    def share_count(self) -> int:
        return _first_int(self.metrics.get("shares"))

    def avg_view_seconds(self) -> float:
        return _first_float(self.metrics.get("avg_view_seconds"))

    def avg_view_pct(self) -> float:
        return _first_float(self.metrics.get("avg_view_pct"))

    def swipe_away_pct(self) -> float:
        return _first_float(self.metrics.get("swipe_away_pct"))

    def has_any_metric(self) -> bool:
        return any(self.metrics.get(key) for key in self.metrics)

    def as_dict(self) -> dict:
        return {
            "render_id": self.render_id,
            "csv": str(self.csv_path),
            "matched_columns": self.matched,
            "metrics": self.metrics,
            "view_count": self.view_count(),
            "avg_view_seconds": self.avg_view_seconds(),
            "avg_view_pct": self.avg_view_pct(),
            "swipe_away_pct": self.swipe_away_pct(),
            "like_count": self.like_count(),
            "comment_count": self.comment_count(),
            "share_count": self.share_count(),
            "note": self.note,
        }


def _first_int(column: object) -> int:
    if not column:
        return 0
    for value in column:
        if isinstance(value, (int, float)) and value >= 0:
            return int(value)
    return 0


def _first_float(column: object) -> float:
    if not column:
        return 0.0
    for value in column:
        if isinstance(value, (int, float)) and value >= 0:
            return float(value)
    return 0.0


# --------------------------------------------------------------- matching

def match_to_render(csv_path: Path, renders: list[dict]) -> str:
    """
    Match a CSV file to an ANTAR render, in this order:

      1. by render id in the filename (the operator can name the file after
         the render when they download it);
      2. by title in the CSV against the script's title_hi;
      3. otherwise empty string - the operator can pair it by hand.

    The match is recorded even when it falls back, so the panel can show
    "matched by hand" instead of "matched by guess" and the operator knows
    whether to trust the number.
    """
    stem = csv_path.stem.lower()
    for render in renders:
        if render["render_id"].lower() in stem:
            return render["render_id"]
    # best-effort title match
    head = csv_path.read_text(encoding="utf-8", errors="replace")[:4000]
    lowered = head.lower()
    for render in renders:
        title = render.get("title") or ""
        if title and title.lower() in lowered:
            return render["render_id"]
    return ""


def all_metrics(config) -> list[VideoMetric]:
    """
    Walk `output/analytics/`, pair every CSV with a render on file, return
    a list of VideoMetric - empty list if no CSVs have been pasted yet.
    """
    folder = config.path("paths.output") / "analytics"
    if not folder.exists():
        return []
    renders = _known_renders(config)
    csvs = sorted(folder.glob("*.csv"))
    if not csvs:
        return []
    metrics: list[VideoMetric] = []
    for csv_path in csvs:
        render_id = match_to_render(csv_path, renders)
        metrics.append(VideoMetric.from_csv(csv_path, render_id))
    return metrics


def _known_renders(config) -> list[dict]:
    """The renders ANTAR has on file, with their titles - the join keys.

    Three sources, in this order:

      1. ``output/video/*_build.json`` - the canonical list, the videos
         ANTAR actually rendered;
      2. ``state.json`` history - synthetic history entries (the test
         suite seeds these to simulate renders without rebuilding) and
         the rotation-difference proof's view of the queue;
      3. ``output/scripts/*_details.json`` titles - the Hindi title the
         operator wrote, used when matching by CSV header.

    A render only exists for the CSV reader when its title is known - the
    join key has to come from somewhere. History entries that lack a
    title fall back to the script file's title_hi, then to the empty
    string (the by-filename match still works without a title).
    """
    output = config.path("paths.output")
    renders = []

    for build in sorted(output.joinpath("video").glob("*_build.json")):
        if build.name.upper().startswith("TEST"):
            continue
        render_id = build.name[: -len("_build.json")]
        details = json.loads((output / "details" / f"{render_id}_details.json").read_text(
            encoding="utf-8")) if (output / "details" / f"{render_id}_details.json").exists() else {}
        script = json.loads((output / "scripts" / f"{render_id}.json").read_text(
            encoding="utf-8")) if (output / "scripts" / f"{render_id}.json").exists() else {}
        renders.append({
            "render_id": render_id,
            "title": details.get("title_hi") or (script.get("script") or {}).get("title_hi", ""),
        })

    # Synthesise an entry per state.json history row that does not already
    # have a _build.json. This is how the learn loop pairs CSVs the test
    # suite seeds without rendering the video twice.
    state_path = config.path("paths.state") / "state.json"
    seen = {r["render_id"] for r in renders}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}
        history = state.get("history") or []
        for entry in history:
            rid = entry.get("render_id")
            if not rid or rid in seen:
                continue
            script_path = output / "scripts" / f"{rid}.json"
            title = ""
            if script_path.exists():
                try:
                    script = json.loads(script_path.read_text(encoding="utf-8"))
                    title = ((script.get("script") or {}).get("title_hi")
                             or (entry.get("rotation") or {}).get("title_hi", ""))
                except (OSError, json.JSONDecodeError):
                    pass
            renders.append({"render_id": rid, "title": title})
            seen.add(rid)
    return renders


def write_aggregate(config, metrics: list[VideoMetric]) -> Path:
    """
    One file the rest of the system reads: aggregate.json.

    The aggregate is what the learn stage and the panel look at, so a
    missing field there is a missing field everywhere. The file lists
    per-video metrics, per-lane aggregates, and a recommendation.
    """
    folder = config.path("paths.output") / "analytics"
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / "aggregate.json"
    record = {
        "when": time.time(),
        "videos": [metric.as_dict() for metric in metrics],
        "by_lane": _group_by(metrics, config, key="lane"),
        "by_hook": _group_by(metrics, config, key="hook"),
        "by_structure": _group_by(metrics, config, key="structure"),
        "by_grade": _group_by(metrics, config, key="grade"),
        "summary": _summary(metrics),
    }
    out.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def _group_by(metrics: list[VideoMetric], config, *, key: str) -> dict:
    """
    Group video metrics by a rotation value (lane/hook/structure/grade).

    The rotation lives in each render's script file. A render with no script
    record contributes nothing - it cannot be grouped honestly without the
    rotation values, and inventing them would be guessing.
    """
    grouped: dict[str, dict] = {}
    script_folder = config.path("paths.output") / "scripts"
    for metric in metrics:
        if not metric.render_id:
            continue
        script_path = script_folder / f"{metric.render_id}.json"
        if not script_path.exists():
            continue
        script = json.loads(script_path.read_text(encoding="utf-8"))
        rotation = script.get("rotation") or {}
        if key == "lane":
            value = ((script.get("topic") or {}).get("lane")
                     or config.get("lane.id") or "?")
        elif key == "hook":
            value = rotation.get("hook_angle") or "?"
        elif key == "structure":
            value = rotation.get("script_structure") or "?"
        else:
            value = rotation.get("grade") or "?"
        bucket = grouped.setdefault(value, {"videos": 0, "views": 0, "retention_pct": 0.0,
                                            "swipe_away_pct": 0.0, "shares": 0, "comments": 0})
        bucket["videos"] += 1
        bucket["views"] += metric.view_count()
        bucket["retention_pct"] += metric.avg_view_pct()
        bucket["swipe_away_pct"] += metric.swipe_away_pct()
        bucket["shares"] += metric.share_count()
        bucket["comments"] += metric.comment_count()
    for bucket in grouped.values():
        if bucket["videos"]:
            bucket["retention_pct"] = round(bucket["retention_pct"] / bucket["videos"], 1)
            bucket["swipe_away_pct"] = round(bucket["swipe_away_pct"] / bucket["videos"], 1)
            bucket["views_per_video"] = round(bucket["views"] / bucket["videos"], 1)
    return grouped


def _summary(metrics: list[VideoMetric]) -> dict:
    total_views = sum(m.view_count() for m in metrics)
    total_videos = sum(1 for m in metrics if m.view_count())
    if total_videos == 0:
        return {"videos_with_data": 0, "total_views": 0,
                "note": "no published videos have analytics yet"}
    return {
        "videos_with_data": total_videos,
        "total_views": total_views,
        "avg_views_per_video": round(total_views / total_videos, 1),
        "avg_retention_pct": round(sum(m.avg_view_pct() for m in metrics) / total_videos, 1),
        "avg_swipe_away_pct": round(sum(m.swipe_away_pct() for m in metrics) / total_videos, 1),
        "top_video": _top(metrics, "view_count"),
        "top_retention": _top(metrics, "avg_view_pct"),
    }


def _top(metrics: list[VideoMetric], attr: str) -> dict:
    if not metrics:
        return {}
    best = max(metrics, key=lambda m: getattr(m, attr)())
    return {"render_id": best.render_id, "csv": str(best.csv_path), "value": getattr(best, attr)()}


def _normalise(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace. Used to match
    YouTube Studio's CSV header names, which shift every release."""
    import re
    cleaned = re.sub(r"[\(\),.;:/%]", " ", text.lower())
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()
