"""
ANTAR - the details stage.

Turns a finished render into the words that go around it: the title, the
description, the tags, the pinned comment, the thumbnail moment.

    from antar.details import run
    payload = run(config, render_id="ANTAR_0001_lane-b-pilot")

What it produces: output/details/<render_id>_details.json

The chain, in order:

    harvest  ->  what people actually search for, live
    candidates ->  five titles, every one scored
    choose   ->  the best, which must clear the Title Score gate
    assemble ->  description, tags, pinned comment, thumbnail
    audit    ->  read it back the way the check suite will

The one rule that runs through all of it: nothing is invented. The title comes
out of phrases real people type; the description comes out of the script and
the topic; the tags come out of the script's own words. If a piece cannot be
built honestly, the stage says which piece and why instead of filling the gap
with filler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .. import log
from ..checks import titlescore
from . import assemble, harvest, writer


class DetailsError(RuntimeError):
    """The details could not be built."""


def _internal_words() -> tuple[str, ...]:
    """The project's own vocabulary - the words that must never be a hashtag."""
    from ..checks.textscan import INTERNAL_WORDS

    return INTERNAL_WORDS


@dataclass
class Result:
    render_id: str
    payload: dict
    path: Path
    audit: list[dict] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(row["pass"] for row in self.audit)

    def failures(self) -> list[dict]:
        return [row for row in self.audit if not row["pass"]]


def _load_json(path: Path) -> dict | None:
    import json

    if not path or not Path(path).exists():
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def newest_script(config) -> Path | None:
    files = sorted((config.path("paths.output") / "scripts").glob("*.json"))
    return files[-1] if files else None


def run(config, render_id: str | None = None, *, brain=None, refresh: bool = False,
        progress=None) -> Result:
    say = progress or (lambda message: None)

    script_path = None
    if render_id:
        candidate = config.path("paths.output") / "scripts" / f"{render_id}.json"
        script_path = candidate if candidate.exists() else None
    script_path = script_path or newest_script(config)
    if not script_path:
        raise DetailsError("no script on file - run: python run.py write")

    script = _load_json(script_path) or {}
    render_id = render_id or script.get("render_id") or script_path.stem
    say(f"script: {script_path.name}")

    # ---------------------------------------------------------------- harvest
    saved = None if refresh else harvest.load(config, render_id)
    if saved and saved.get("phrases"):
        say(f"harvest: reusing {len(saved['phrases'])} saved suggestion(s) "
            f"({saved.get('note', '')})")
        harvest_payload = saved
    else:
        say("harvest: asking the live autocomplete endpoint")
        harvest_payload = harvest.harvest(script)
        harvest.save(config, render_id, harvest_payload)
        say("harvest: " + harvest_payload.get("note", ""))
    # The phrases the BUILDER uses and the phrases the JUDGE scores against are
    # the same list - an earlier version scored against the raw harvest while
    # building with one more phrase, so the best title in the run was marked
    # "contains no harvested search phrase" for a phrase it plainly contained.
    phrases = list(harvest_payload.get("phrases") or [])
    topic_phrase = ((script.get("topic") or {}).get("search_phrase_hi") or "").strip()
    if topic_phrase and topic_phrase not in phrases:
        # the topic's own phrase was tested against the same autocomplete
        # endpoint when the topic was chosen, so it is a real search phrase
        phrases.append(topic_phrase)
        harvest_payload["topic_phrase_added"] = topic_phrase
    harvest_payload["phrases"] = phrases
    harvest_payload["scored_against"] = phrases

    # ------------------------------------------------------------- candidates
    scored, chosen, written_by = writer.candidates(brain, phrases, script)
    if not scored:
        raise DetailsError("no title candidate could be built from this script")
    for line in writer.lines(scored):
        say(line)

    best = scored[0]
    chosen = best["title"]
    say(f"chosen: {chosen}  ({best['total']}/100, target {titlescore.GENERATOR_TARGET})")
    if best["total"] < titlescore.SCORE_MIN:
        log.warn(f"details: the best title scored {best['total']}, under the "
                 f"{titlescore.SCORE_MIN} gate - the check suite will refuse it")

    # --------------------------------------------------------------- assemble
    plan = _load_json(config.path("paths.output") / "plans" / f"{render_id}_picture.json")
    build_record = _load_json(config.path("paths.output") / "video" / f"{render_id}_build.json")
    payload = assemble.build(config, script, scored, chosen, written_by,
                             harvest_payload, plan or {}, build_record or {}, render_id)

    audit = assemble.audit(payload)
    payload["audit"] = audit

    path = write(config, render_id, payload)
    return Result(render_id=render_id, payload=payload, path=path, audit=audit)


def write(config, render_id: str, payload: dict) -> Path:
    import json

    folder = config.path("paths.output") / "details"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{render_id}_details.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    temporary.replace(path)
    return path


def load(config, render_id: str) -> dict | None:
    return _load_json(config.path("paths.output") / "details" / f"{render_id}_details.json")
