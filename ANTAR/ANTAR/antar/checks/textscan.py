"""
ANTAR - reading the words that will be public, before the public does.

Two blocking rules live here, and both of them exist because of a real
mistake:

  * internal labels must never ship. `#Contrarian` went out publicly once - a
    lane name, on a real video, in front of real people. So the scan looks for
    the project's own vocabulary (render ids, lane slugs, stage names, file
    extensions, hashtags, code words) in everything a viewer could see.
  * names must never appear. "Carlos" spent the only public line of a video on
    a stranger. The list of forbidden names is the project's own list from the
    script stage, not a second one written here.

The scan does not guess and it does not summarise. It returns every hit with
the exact text and where it was found, so a failure can be looked at instead of
argued with.
"""

from __future__ import annotations

import re

# The project's own words. If one of these reaches a viewer, it is a leak.
INTERNAL_WORDS = (
    "render_id", "lane-b", "lane b", "practical-psychology", "practical psychology",
    "beat", "hook", "payoff", "build", "fixture", "placeholder", "todo", "fixme",
    "none", "nan", "undefined", "null",
    "phase 1", "phase 2", "phase 3", "phase 4", "phase 5", "phase 6",
    "antar_", "khand", "edge-tts", "edge tts", "pexels", "pixabay", "gemini", "groq",
    "swara", "lufs", "json", "mp4", "wav", "png", "vault", "registry", "prompt",
    "model", "api", "slug", "audit", "scorecard", "rotation", "template",
)

# Things that look like code, whatever the words are.
CODE_SHAPES = (
    (r"#\w+", "hashtag"),
    (r"\b[a-z0-9_]+\.(json|mp4|wav|png|py|md|txt)\b", "file name"),
    (r"\b[A-Z]{2,}_[A-Z0-9_]+\b", "constant"),
    (r"\{[^}]*\}", "placeholder braces"),
    (r"\[[^\]]*\]", "brackets"),
    (r"\b[\w\-]+/[\w\-]+\b", "path"),
    (r"\bANTAR\b", "project name"),
)


def _items(texts) -> list[tuple[str, str]]:
    """Accept a dict {where: text} or a list of (where, text)."""
    if isinstance(texts, dict):
        return [(where, text or "") for where, text in texts.items()]
    return [(where, text or "") for where, text in texts]


def _found_word(low: str, needle: str) -> int:
    """
    Where a needle appears - on a word boundary for Latin words.

    Substring matching flagged "capital" for containing "api" and would flag
    any English tag that happens to contain a short internal word. A word
    boundary is what makes the scan usable on real text; Devanagari and
    multi-word needles are matched as substrings, because that is how they
    genuinely appear.
    """
    needle = needle.lower()
    if not needle:
        return -1
    if any(ord(c) > 127 for c in needle) or " " in needle:
        return low.find(needle)
    index = -1
    for match in re.finditer(rf"(?<![a-z0-9_]){re.escape(needle)}(?![a-z0-9_])", low):
        index = match.start()
        break
    return index


def leaks(texts, extra_slugs: list[str] | None = None) -> list[dict]:
    """
    Every internal label a viewer could see. Empty list means clean.

    `extra_slugs` carries the values that belong to this render - its id, its
    lane, its file names - so a leaking render id is caught by value, not only
    by shape.

    A hashtag is only a leak when the word behind it is one: "#Contrarian" is
    the mistake this rule exists for, while a Devanagari subject hashtag is
    what the details stage is supposed to produce. All-Latin words are still
    reported, because on a Hindi video a Latin word in public text needs a
    person to look at it.
    """
    hits: list[dict] = []
    needles = list(INTERNAL_WORDS) + [s for s in (extra_slugs or []) if s]

    for where, text in _items(texts):
        if not text.strip():
            continue
        low = text.lower()
        for needle in needles:
            index = _found_word(low, needle)
            if index >= 0:
                snippet = text[max(0, index - 24):index + 40]
                hits.append({"where": where, "found": needle,
                             "kind": "internal word", "snippet": " ".join(snippet.split())})
        for pattern, kind in CODE_SHAPES:
            for match in re.finditer(pattern, text):
                token = match.group(0)
                if kind == "hashtag":
                    word = token.lstrip("#")
                    # A Latin hashtag is always reported: on a Hindi channel the
                    # subject hashtags are Devanagari, so "#Contrarian" or
                    # "#shorts" in public text is somebody's internal label or
                    # somebody's keyword dump. A Devanagari hashtag is only a
                    # leak when the word behind it is one of ours.
                    if word.isascii():
                        pass
                    elif not any(_found_word(word.lower(), n) == 0 or word.lower() in n.lower()
                                 for n in needles):
                        continue
                if any(hit["found"].lower() == token.lower() and hit["where"] == where
                       for hit in hits):
                    continue
                hits.append({"where": where, "found": token, "kind": kind,
                             "snippet": " ".join(text[max(0, match.start() - 20):
                                                         match.end() + 24].split())})
    return hits


def names(texts) -> list[dict]:
    """
    Person names in public text. Empty list means none.

    Anything in Latin script is reported too: this script is written in Hindi,
    so a Latin word on screen is either a name, a brand or a leak, and all
    three need a human to look at them before upload.
    """
    try:
        from ..brain.objects import find_banned_names
    except Exception:                       # pragma: no cover - only if moved
        find_banned_names = lambda text: []  # noqa: E731

    hits: list[dict] = []
    for where, text in _items(texts):
        if not text.strip():
            continue
        for found in find_banned_names(text):
            hits.append({"where": where, "found": found, "kind": "forbidden name"})
        for match in re.finditer(r"\b[A-Za-z][A-Za-z'\-]{2,}\b", text):
            token = match.group(0)
            hits.append({"where": where, "found": token, "kind": "latin script"})
    return hits


def devanagari_ratio(text: str) -> float:
    """How much of the text is Devanagari. The lane writes in Hindi."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    hindi = [c for c in letters if 0x0900 <= ord(c) <= 0x097F]
    return len(hindi) / len(letters)


def words(text: str) -> list[str]:
    """Plain words, punctuation stripped."""
    return [w for w in re.split(r"[\s।,!?;:\-\(\)\"']+", text or "") if w]
