"""
ANTAR - the search box test.

The rule: a topic is only allowed if a real person would type those words into
YouTube. This module answers that question with evidence instead of opinion.

It asks YouTube's own autocomplete endpoint. If typing your phrase makes real
suggestions appear, people are searching for things shaped like it. If nothing
comes back, the phrase exists only in your head.

This is the single most useful thing in the engine, because search is the one
surface where a small channel is not competing against millions of creators.

No API key is needed and nothing is stored.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

SUGGEST = ("https://suggestqueries.google.com/complete/search"
           "?client=youtube&ds=yt&hl=hi&q={query}")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def _parse(raw: str) -> list[str]:
    """
    Pull suggestions out of the endpoint's reply.

    The endpoint returns JavaScript-ish JSON:  window.google.ac.h([...]).
    Some mirrors return plain JSON. Both are handled, and anything else
    returns an empty list rather than raising.
    """
    if not raw:
        return []
    start = raw.find("(")
    end = raw.rfind(")")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(raw[start + 1:end])
        except json.JSONDecodeError:
            return []
    else:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []

    if not isinstance(data, list) or len(data) < 2:
        return []
    out: list[str] = []
    for item in data[1]:
        if isinstance(item, list) and item:
            out.append(str(item[0]))
        elif isinstance(item, str):
            out.append(item)
    return out


def suggest(phrase: str, timeout: int = 10) -> list[str]:
    """
    Live autocomplete suggestions for a Hindi phrase. An empty list means
    nothing - either nobody searches it, or the network failed. The caller
    cannot tell the difference, so it treats both as 'unproven'.
    """
    url = SUGGEST.format(query=urllib.parse.quote(phrase))
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
    except Exception:
        return []
    return _parse(raw)


def _tokens(text: str) -> set[str]:
    import re
    return {t for t in re.split(r"[\s,।?]+", text.strip()) if len(t) > 2}


def test(phrase: str, extra_probes: list[str] | None = None) -> dict:
    """
    Score how searchable a phrase is.

    Returns:
        {
          "phrase": ...,
          "suggestions": [...],
          "hits": how many suggestions relate to the phrase,
          "signal": "strong" | "present" | "thin" | "none",
          "probes": {probe: [suggestions]},
        }

    The signal is a count, not an opinion:
        strong   three or more related suggestions
        present  one or two
        thin     suggestions exist but none relate to the phrase
        none     nothing came back
    """
    phrase_tokens = _tokens(phrase)
    suggestions = suggest(phrase)

    hits = 0
    for item in suggestions:
        item_tokens = _tokens(item)
        if phrase_tokens & item_tokens:
            hits += 1

    if hits >= 3:
        signal = "strong"
    elif hits >= 1:
        signal = "present"
    elif suggestions:
        signal = "thin"
    else:
        signal = "none"

    probes: dict[str, list[str]] = {}
    for probe in (extra_probes or []):
        probes[probe] = suggest(probe)

    return {
        "phrase": phrase,
        "suggestions": suggestions,
        "hits": hits,
        "signal": signal,
        "probes": probes,
    }


def related_vocabulary(seeds: list[str]) -> set[str]:
    """
    Harvest the words real people use when searching this lane.

    Feed it a few roots; it returns every word that appears in the
    suggestions. This is how the topic engine learns the audience's actual
    language instead of inventing it.
    """
    vocabulary: set[str] = set()
    for seed in seeds:
        for suggestion in suggest(seed):
            vocabulary |= _tokens(suggestion)
    return vocabulary
