"""
ANTAR - harvesting what people actually type.

35 of the Title Score's 100 points come from containing a phrase real people
search for, so the harvest is not decoration - it is most of the score.

Where the phrases come from:

  1. YouTube's own autocomplete, live, keyless, in Hindi. This is the honest
     source: if a phrase appears there, people type it.
  2. The script's own topic phrases, as a floor, because they were already
     tested against the same endpoint when the topic was chosen.
  3. Nothing else. If the network is down the harvest is empty, the 35 points
     score zero, and the run says so. An invented "popular phrase" would be a
     lie dressed as research.

Every harvest is saved with its source and time, so a title can always be
traced back to the phrases that produced it.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .. import log
from ..brain import searchbox

# The words the harvest walks through after the root phrase. Hindi searchers
# type the start of a question far more often than a whole sentence.
PROBES = ("क्यों", "कैसे", "कब", "क्या", "कहाँ")

# Words so common that sharing one proves nothing about the topic. A suggestion
# only counts when it shares a word that is NOT in here - that is how a phrase
# about मोहब्बत stops being collected for a video about being ignored.
STOPWORDS = {
    "लोग", "क्यों", "कैसे", "कब", "क्या", "कौन", "कहाँ", "कहां", "किसे", "किसने",
    "करते", "करता", "करती", "किया", "है", "हैं", "हो", "होता", "होती", "था", "थी",
    "में", "का", "की", "के", "को", "से", "और", "पर", "तुम", "वो", "ये", "एक", "भी",
    "नहीं", "कभी", "बार", "बात", "साथ", "लिए", "जब", "तब", "अब", "फिर", "सब", "कुछ",
}


def _content_words(text: str) -> set[str]:
    import re

    return {w for w in re.split(r"[\s।,!?;:\-]+", (text or "").lower())
            if len(w) > 2 and w not in STOPWORDS}


def _vocabulary(*texts: str) -> set[str]:
    """Every content word the video is genuinely about."""
    words: set[str] = set()
    for text in texts:
        words |= _content_words(text)
    return words


def _allowed(text: str, vocabulary: set[str]) -> bool:
    """
    Is every content word of this suggestion a word of this video?

    Sharing one distinctive word is not enough - that is how "लोग इग्नोर क्यों
    करते हैं कबूतर" (a real suggestion about pigeons) was collected for a video
    about being ignored, and it would have gone out as the title. A suggestion
    is used only when every content word in it appears in the topic or the
    script. A pigeon is not in the script.
    """
    if not vocabulary:
        return True
    extra = _content_words(text) - vocabulary
    return not extra


class HarvestError(RuntimeError):
    """The harvest could not run."""


def root_phrases(script: dict) -> list[str]:
    """The starting points, taken from the topic this script was written for."""
    topic = (script or {}).get("topic") or {}
    roots = [topic.get("search_phrase_hi", ""), topic.get("title_hi", ""),
             topic.get("mechanism_hi", "")]
    return [r.strip() for r in roots if r and r.strip()][:3]


def vocabulary_for(script: dict) -> set[str]:
    """
    Every content word this video is genuinely about: its topic, its mechanism
    and its script. One function, because the collector and the title writer
    must never disagree about what counts as on-topic - an earlier version
    filtered at collection time only, so a stale harvest file could put an
    off-topic phrase into a title.
    """
    beats = ((script or {}).get("script") or {}).get("beats") or []
    topic = (script or {}).get("topic") or {}
    return _vocabulary(*root_phrases(script), topic.get("title_hi", ""),
                       topic.get("mechanism_hi", ""),
                       *[b.get("line_hi", "") for b in beats])


def harvest(script: dict, *, extra_probes: list[str] | None = None,
            pause: float = 0.15, limit_per_probe: int = 8) -> dict:
    """
    Ask the live endpoint for suggestions. Network failure is not an exception
    here - it is an empty harvest with a reason, because the stage must still
    produce details when the connection is down.

    Two things this deliberately does NOT do, both learned the hard way:

      * it does not query a one-or-two-word stem of the topic. Asking YouTube
        about "लोग" returns suggestions about love, food, memory and
        nationality - all real searches, none of them this video. Every query
        is the topic's own phrase, with a probe word appended.
      * it does not keep a suggestion just because the endpoint returned it.
        A suggestion counts only when it shares a distinctive word with the
        topic. The ones rejected are counted and reported, not silently used.
    """
    roots = root_phrases(script)
    if not roots:
        return {"phrases": [], "sources": [], "note": "the script names no topic to harvest from",
                "when": time.time()}

    vocabulary = vocabulary_for(script)

    probes = list(PROBES if extra_probes is None else extra_probes)
    phrases: list[str] = []
    sources: list[dict] = []
    off_topic = 0
    empty = 0

    for root in roots:
        for probe in ["", *probes]:
            query = f"{root} {probe}".strip()
            try:
                found = searchbox.suggest(query)
            except Exception:
                found = []
            if not found:
                empty += 1
                time.sleep(pause)
                continue
            kept = 0
            for suggestion in found[:limit_per_probe]:
                text = " ".join(str(suggestion).split())
                if not text:
                    continue
                if not _allowed(text, vocabulary):
                    off_topic += 1
                    continue
                if text not in phrases:
                    phrases.append(text)
                    kept += 1
            sources.append({"query": query, "found": len(found), "kept": kept, "live": True})
            time.sleep(pause)

    note = (f"{len(phrases)} live suggestion(s) kept from {len(sources)} query(ies), "
            f"{off_topic} off-topic suggestion(s) rejected")
    if not phrases:
        note = ("nothing on-topic came back from the autocomplete endpoint - the "
                "harvest is empty, so the search-phrase points will come from the "
                "topic's own search phrase, which was tested when the topic was chosen")
        log.warn("details: " + note)
    elif empty > len(sources):
        note += f"; {empty} query(ies) returned nothing"

    return {"phrases": phrases, "sources": sources, "note": note,
            "off_topic_rejected": off_topic, "roots": roots,
            "vocabulary": sorted(vocabulary)[:60], "when": time.time()}


def save(config, render_id: str, payload: dict) -> Path:
    folder = config.path("paths.output") / "details"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{render_id}_harvest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load(config, render_id: str) -> dict | None:
    """A saved harvest for this render, if there is one - so a re-run is cheap."""
    path = config.path("paths.output") / "details" / f"{render_id}_harvest.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
