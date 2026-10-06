"""
ANTAR - the title candidates.

Five candidates, every one scored with the same judge the check suite uses, all
five shown with their numbers, the best one selected. The plan's words: "Show
all 5 with scores; highest pre-selected."

Two ways to make them:

  * **with a writing model** - one call, the harvested phrases handed to it as
    the raw material, the reply parsed into five titles;
  * **without one** - built from the harvest and the script's own lines. The
    engine is not allowed to stop producing details because every key is down,
    and it is not allowed to pretend a model wrote something it did not.

Either way the candidates are only proposals. The scorer decides.
"""

from __future__ import annotations

import re

from .. import log
from ..checks import titlescore
from . import harvest
from ..checks.textscan import leaks, names

CANDIDATE_COUNT = 5


def _clean(text: str) -> str:
    text = " ".join((text or "").split())
    text = re.sub(r"^[\-\*\d\.\)\s]+", "", text)          # list bullets, numbers
    text = text.strip(" \t\"'`|")
    return text


def from_model(brain, phrases: list[str], script: dict, *, count: int = CANDIDATE_COUNT) -> tuple[list[str], str]:
    """Ask a writing model for candidates. Returns (titles, who wrote them)."""
    if brain is None:
        return [], ""

    topic = (script or {}).get("topic") or {}
    prompt = (
        "नीचे असली YouTube सर्च सुझाव हैं (लोग ये असल में टाइप करते हैं):\n"
        + "\n".join(f"- {p}" for p in phrases[:20])
        + "\n\nइस वीडियो का विषय: " + topic.get("title_hi", "")
        + "\n\n"
        f"{count} अलग-अलग टाइटल लिखो। हर टाइटल:\n"
        "- में ऊपर के किसी सुझाव के शब्द प्राकृतिक रूप से हों\n"
        "- 30 से 48 अक्षर का हो\n"
        "- सवाल या उलटी बात जैसा लगे\n"
        "- एक भावना वाला शब्द रखे (चुप्पी, नज़रअंदाज़, कीमत, अकेलापन)\n"
        "- फ़ोन, मग, दीवार, खिड़की जैसे फुटेज शब्द कभी नहीं\n"
        "- तुम से बात करे, आप कभी नहीं\n"
        "- कोई नाम, हैशटैग, इमोजी नहीं\n\n"
        'सिर्फ़ JSON लौटाओ: {"titles": ["...", "...", "...", "...", "..."]}'
    )
    ok, text, note = brain.call(prompt, None, None, temperature=0.9, max_tokens=700)
    if not ok:
        return [], note
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return [], "the reply had no JSON in it"
    import json

    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return [], "the reply's JSON would not parse"
    titles = [_clean(t) for t in (payload.get("titles") or []) if isinstance(t, str)]
    return [t for t in titles if t][:count], f"model ({getattr(brain, 'last_model', 'unknown')})"


def usable_phrases(phrases: list[str], script: dict) -> list[str]:
    """
    The phrases a Hindi title can actually be built on.

    Three filters, each for a real reason:

      * Devanagari only - the title is Devanagari, so a romanised suggestion
        ("log ignore kyu karte hai") cannot appear in it, however real it is;
      * two words or more - a one-word fragment is not a search phrase, and an
        earlier version of this stage built titles around one;
      * no footage nouns - a harvested phrase containing "फ़ोन" would put a
        footage word in the headline, which costs the title its points;
      * on topic - every word of the phrase must belong to this video. The
        harvest applies this when it collects, and the writer applies it again
        when it builds, because a phrase list on disk can be stale or edited
        by hand and a pigeon must not be able to reach a title.
    """
    objects = [b.get("object_hi", "") for b in
               ((script or {}).get("script") or {}).get("beats") or []]
    vocabulary = harvest.vocabulary_for(script)
    out: list[str] = []
    for phrase in phrases:
        text = " ".join((phrase or "").split())
        if len(text) < 12 or len(text.split()) < 2:
            continue
        if not re.search(r"[\u0900-\u097F]", text):
            continue
        if any(obj and obj in text for obj in objects):
            continue
        if not harvest._allowed(text, vocabulary):
            continue
        if text not in out:
            out.append(text)
    out.sort(key=len, reverse=True)
    return out


# Every shape reads like Hindi and carries a feeling word, so a title built on
# a whole harvested phrase can reach the top of the score without being padded.
SHAPES = (
    "{phrase} और तुम्हारी चुप्पी का सच",
    "{phrase} — चुप्पी की असली वजह",
    "{phrase} और अकेलेपन का सच",
    "{phrase} — नज़रअंदाज़ की कीमत",
    "{phrase}, और तुम चुप क्यों रहते हो",
    "{phrase} का जवाब तुम्हारी चुप्पी में",
    "{phrase} — जवाब जो तुमने कभी नहीं दिया",
)


def from_script(phrases: list[str], script: dict, *, count: int = CANDIDATE_COUNT) -> list[str]:
    """
    Build candidates with no model: a whole harvested phrase, plus a shape that
    reads like Hindi and carries a feeling.

    The phrase stays intact - that is what earns the 35 search points - and the
    shape is chosen so the finished title lands inside the length band rather
    than being trimmed into nonsense.
    """
    topic = (script or {}).get("topic") or {}
    low, high = 30, 48
    usable = usable_phrases(phrases, script)
    topic_phrase = (topic.get("search_phrase_hi") or "").strip()
    if topic_phrase and topic_phrase not in usable:
        # the topic's own phrase was tested against the same endpoint when the
        # topic was chosen, so it is a real search phrase and belongs here
        usable.append(topic_phrase)

    candidates: list[str] = []
    for phrase in usable:
        ranked = sorted(SHAPES, key=lambda shape: abs(len(shape.format(phrase=phrase)) - 39))
        for shape in ranked:
            text = shape.format(phrase=phrase)
            if low <= len(text) <= high and text not in candidates:
                candidates.append(text)
                break
        if len(candidates) >= count:
            break

    # if the harvest was thin, the topic's own search phrase carries the rest
    if len(candidates) < count:
        fallback = (topic.get("search_phrase_hi") or "").strip()
        if fallback and len(fallback.split()) >= 2:
            for shape in SHAPES:
                text = shape.format(phrase=fallback)
                if low <= len(text) <= high and text not in candidates:
                    candidates.append(text)
                if len(candidates) >= count:
                    break

    seen: list[str] = []
    for title in candidates:
        title = _clean(title)
        if not title or title in seen:
            continue
        if leaks({"t": title}) or names({"t": title}):
            continue
        if len(title) < low:
            continue
        seen.append(title)
    return seen[:count]


def candidates(brain, phrases: list[str], script: dict, *,
               count: int = CANDIDATE_COUNT) -> tuple[list[dict], str, str]:
    """
    Every candidate, scored. Returns (scored_candidates, best_title, written_by).

    Model candidates and built candidates are both scored; if the model's are
    worse, the built ones win. The best title is the highest score, and ties go
    to the model's, because a person would rather read something written than
    something assembled.
    """
    model_titles, who = from_model(brain, phrases, script, count=count)
    built = from_script(phrases, script, count=count)

    merged: list[tuple[str, str]] = []
    for title in model_titles:
        merged.append((title, "model"))
    for title in built:
        if title not in [t for t, _ in merged]:
            merged.append((title, "built"))
    if not merged:
        return [], "", who or "nothing"

    footage_words = [b.get("object_hi", "") for b in
                     ((script or {}).get("script") or {}).get("beats") or []]

    scored: list[dict] = []
    for title, origin in merged[:count * 2]:
        result = titlescore.score(title, _config(), phrases=phrases,
                                 footage_words=footage_words)
        result["origin"] = origin
        scored.append(result)
    scored.sort(key=lambda r: (-r["total"], 0 if r["origin"] == "model" else 1))

    best = scored[0]["title"] if scored else ""
    written = who if any(r["origin"] == "model" for r in scored) else "built from the harvest and the script"
    return scored[:count], best, written


_cached_config = None


def _config():
    global _cached_config
    if _cached_config is None:
        from .. import config as configmod

        _cached_config = configmod.load()
    return _cached_config


def lines(scored: list[dict]) -> list[str]:
    out: list[str] = []
    for rank, row in enumerate(scored, start=1):
        mark = "->" if rank == 1 else "  "
        out.append(f"{mark} {row['total']:3}/100  [{row['origin']:5}] {row['title']}")
        weakest = sorted(row["parts"], key=lambda p: p["points"] / p["of"])[0]
        out.append(f"        {row['characters']} chars; weakest: {weakest['part']} - "
                   f"{weakest['note'][:64]}")
    return out
