"""
ANTAR - the writer.

Two rules, both of them scars:

  1. The strongest model a key is entitled to must write every script.
     If a weak model answers first, the engine keeps climbing. A cheap answer
     is never accepted just because it arrived.

  2. A quality gate must never end a run with nothing. The best draft of the
     run is kept and returned even when it is not perfect; the audit's
     complaints are carried alongside it and shown, not hidden.

How a script is chosen:
    models are tried strongest first, up to `attempts` of them
    every draft is audited and scored
    a draft that passes cleanly wins immediately
    otherwise the best-scoring draft of the whole run is returned
    a too-short draft is sent back once for extension before scoring
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .. import log
from . import audit, models, prompts
from .providers import Brain, extract_json
from .topics import Topic


@dataclass
class Draft:
    script: dict
    report: audit.Report
    model: str
    service: str
    attempt: int
    repaired: bool = False
    note: str = ""

    @property
    def score(self) -> int:
        return self.report.score()

    @property
    def clean(self) -> bool:
        return not self.report.blocked and not self.report.of("WARN")


@dataclass
class Result:
    script: dict | None
    report: audit.Report | None
    model: str = ""
    service: str = ""
    attempts: list[str] = field(default_factory=list)
    drafts: int = 0
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.script is not None

    def summary(self) -> str:
        if not self.ok:
            return f"no usable script - {self.note}"
        flags = len(self.report.of("WARN")) if self.report else 0
        return (f"{self.report.words} words, {self.report.beats} beats, "
                f"score {self.report.score()}/100, {flags} warning(s), "
                f"written by {self.service}/{self.model}")


def write(brain: Brain, topic: Topic, config, structure: str | None = None,
          hook_angle: str | None = None) -> Result:
    """Write one script for one topic."""
    cfg = config.get("brain", {}) or {}
    pacing = config.get("pacing", {}) or {}

    band = pacing.get("band_words") or [78, 102]
    floor = int(pacing.get("render_floor_words", band[0] - 8))
    ceiling = int(pacing.get("render_ceiling_words", band[1] + 8))
    target = int(round((band[0] + band[1]) / 2))

    prefer = cfg.get("prefer_models", []) or []
    max_attempts = int(cfg.get("write_attempts", 4))
    allow_repair = bool(cfg.get("repair_short_drafts", True))

    ladder = models.ladder(brain, prefer)
    if not ladder:
        return Result(None, None, note="no models available - every key down or unreachable")

    result = Result(None, None)
    best: Draft | None = None

    structure = structure or topic.structure or "problem-mechanism"
    hook_angle = hook_angle or topic.hook_angle or "direct-question"

    prompt = prompts.writer_prompt(
        topic=topic.topic_hi, question=topic.question_hi, mechanism=topic.mechanism_hi,
        hook_angle=hook_angle, structure=structure,
        target_words=target, floor=floor, ceiling=ceiling)

    for attempt, candidate in enumerate(ladder[:max_attempts], start=1):
        ok, text, note = brain.call(
            prompt, candidate.model, candidate.service,
            system=prompts.WRITER_SYSTEM, temperature=0.85, max_tokens=2500)

        if not ok:
            result.attempts.append(f"{candidate.service}/{candidate.model}: {note}")
            log.warn(f"writer: {candidate.service}/{candidate.model} -> {note}")
            continue

        script = extract_json(text)
        if not script or not script.get("beats"):
            result.attempts.append(f"{candidate.service}/{candidate.model}: unparseable reply")
            log.warn(f"writer: {candidate.service}/{candidate.model} returned no usable JSON")
            continue

        report = audit.audit(script, floor, ceiling, tuple(band))
        draft = Draft(script, report, candidate.model, candidate.service, attempt)

        # a draft that is too short gets one chance to grow, on the same model
        if allow_repair and report.blocked and any(f.check == "length" and "floor" in f.detail
                                                   for f in report.findings):
            log.info(f"writer: draft is {report.words} words, below the floor of {floor} - asking it to extend")
            extended = _extend(brain, candidate, script, report.words, floor, ceiling)
            if extended is not None:
                new_report = audit.audit(extended, floor, ceiling, tuple(band))
                if new_report.words > report.words:
                    draft = Draft(extended, new_report, candidate.model, candidate.service,
                                  attempt, repaired=True)
                    log.ok(f"writer: extended to {new_report.words} words")

        result.drafts += 1
        result.attempts.append(
            f"{candidate.service}/{candidate.model}: {draft.report.words} words, "
            f"score {draft.score}, {'blocked' if draft.report.blocked else 'usable'}"
            + (" (repaired)" if draft.repaired else ""))
        log.info(f"writer: {candidate.service}/{candidate.model} -> "
                 f"{draft.report.words} words, score {draft.score}"
                 f"{', blocked' if draft.report.blocked else ''}")

        if best is None or draft.score > best.score:
            best = draft

        if draft.clean:
            log.ok(f"writer: clean draft on attempt {attempt} from {candidate.service}/{candidate.model}")
            return _finish(draft, result, candidate.service)

    # no clean draft. keep the best one rather than ending with nothing.
    if best is not None:
        if best.report.blocked:
            log.warn(f"writer: best draft is blocked ({best.report.words} words) - "
                     f"it will be returned with its complaints attached")
        else:
            log.warn(f"writer: no clean draft after {result.drafts} attempt(s) - "
                     f"returning the best, score {best.score}/100")
        return _finish(best, result, best.service)

    result.note = "; ".join(result.attempts) or "every model failed"
    return result


def _finish(draft: Draft, result: Result, service: str) -> Result:
    result.script = draft.script
    result.report = draft.report
    result.model = draft.model
    result.service = service
    return result


def _extend(brain: Brain, candidate, script: dict, words: int,
            floor: int, ceiling: int) -> dict | None:
    """Send a too-short draft back, once, asking it to grow rather than shrink."""
    prompt = prompts.repair_prompt(json.dumps(script, ensure_ascii=False, indent=2),
                                   words, floor, ceiling)
    ok, text, note = brain.call(
        prompt, candidate.model, candidate.service,
        system=prompts.WRITER_SYSTEM, temperature=0.7, max_tokens=2500)
    if not ok:
        return None
    return extract_json(text)


def to_plain_text(script: dict) -> str:
    """The script as a human reads it - used by the panel and by nothing else."""
    lines = []
    for beat in script.get("beats", []):
        role = (beat.get("role") or "").upper()
        lines.append(f"[{role:6}] {beat.get('line_hi', '')}")
        obj = beat.get("object_hi")
        if obj:
            lines.append(f"         object: {obj}")
    return "\n".join(lines)
