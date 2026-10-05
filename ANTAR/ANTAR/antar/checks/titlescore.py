"""
ANTAR - the Title Score, to the master plan's own table.

The plan lists the criteria and the points. This file is that table, written
once, used twice - by the generator that proposes titles and by the check
suite that can refuse to upload them. One judge, so the generator cannot talk
its way past the gate.

    contains a harvested search phrase   35
    40-60 characters (the feed's width)  15
    question or contrarian shape         15
    emotion word present                 10
    no footage nouns                     10
    no names                             10
    banned phrases absent                 5

Two notes on carrying that table across honestly:

  * **The character band.** The plan says 40-60 characters, which is a DISPLAY
    WIDTH rule from English. A Devanagari glyph is about 1.3x the width of a
    Latin one at the same size, so the project's config derives the band
    30-48 and this scorer reads it from there. The number is different; the
    rule is the same.
  * **The harvested phrase.** 35 of the 100 points come from containing
    something real people actually type. If no harvest is available the
    criterion scores zero and says so - it is not quietly given away.

Anything that cannot be measured is reported, never assumed.
"""

from __future__ import annotations

import re

from . import textscan

SCORE_MIN = 70          # config: thresholds.title_score_min
GENERATOR_TARGET = 80   # master plan, Phase 7 exit criteria

# Hindi words that carry a feeling or a stake. The lane writes about being
# ignored, being spoken over, and the price of staying quiet - the vocabulary
# that belongs to that is what this list holds.
EMOTION_WORDS = (
    "नज़रअंदाज़", "नजरअंदाज", "इग्नोर", "अकेला", "अकेले", "अकेलापन", "चुप्पी", "चुप",
    "डर", "डरते", "गुस्सा", "अपमान", "बेइज़्ज़ती", "शर्म", "इंतज़ार", "थकान", "दर्द",
    "टूट", "जलन", "ईर्ष्या", "मायूस", "उम्मीद", "उम्मीदें", "ताकत", "कीमत", "इज़्ज़त",
    "रिश्ता", "रिश्ते", "अपना", "अपनापन", "दूरी", "जवाब", "खालीपन", "तनहाई", "सुकून",
    "गलती", "सच", "झूठ", "भरोसा", "बदल", "कमज़ोर", "मज़बूत", "हार",
)

# Shapes that make a title a question or a claim that pushes back.
QUESTION_WORDS = ("क्यों", "कैसे", "कब", "कौन", "क्या", "कहाँ", "कहां", "किसने", "किसे")
CONTRARIAN_WORDS = ("सच", "गलती", "झूठ", "सच्चाई", "कोई नहीं", "नहीं चाहता", "नहीं बताता",
                    "बंद करो", "छोड़ दो", "मत", "कभी नहीं", "उलटा", "गलत", "बेकार")

# Framing the lane banned outright, plus anything from the project's own
# vocabulary that must never reach a viewer.
BANNED_PHRASES = ("स्टोइक", "डार्क साइकोलॉजी", "डार्क साइकोलॉजि", "अल्फा", "सिग्मा",
                  "मैनिपुलेशन", "गैसलाइटिंग", "टॉक्सिक", "बॉस", "बिज़नेस", "पैसा कमाओ",
                  "life hacks", "motivation")


def _band(config) -> tuple[int, int]:
    return (int(config.get("topics.title_min_chars", 30)),
            int(config.get("topics.title_max_chars", 48)))


def _normal(text: str) -> str:
    """Lowercase, punctuation out - for matching, never for display."""
    return " ".join(re.split(r"[\s।,!?;:\-\(\)\"']+", (text or "").lower())).strip()


MIN_PHRASE_CHARS = 12      # a real search phrase, not a fragment
MIN_PHRASE_WORDS = 2


def phrase_hit(title: str, phrases: list[str]) -> tuple[str, str, float]:
    """
    The longest harvested phrase this title contains, and how fully.

    A WHOLE phrase - two words or more, twelve characters or more - is what the
    plan's 35 points are for. A fragment ("इग्नोर" on its own, or three loose
    words in the right order) is worth part of it and says so, because an
    earlier version of this scorer handed 35 points to a one-word match and the
    generator happily produced titles assembled around a fragment.
    """
    if not title or not phrases:
        return "", "no harvest was available", 0.0

    low = _normal(title)
    best_whole = ""
    best_partial = ""
    for phrase in phrases:
        clean = _normal(phrase)
        words = [w for w in clean.split() if w]
        if len(clean) < MIN_PHRASE_CHARS or len(words) < MIN_PHRASE_WORDS:
            continue
        if clean in low:
            if len(clean) > len(best_whole):
                best_whole = phrase
            continue
        if len(words) >= 3:
            position = 0
            matched = 0
            for word in words:
                found = low.find(word, position)
                if found != -1:
                    matched += 1
                    position = found + len(word)
            if matched >= max(3, len(words) - 1) and len(words) > len(best_partial.split()):
                best_partial = phrase

    if best_whole:
        return (best_whole,
                f"contains the harvested phrase \"{best_whole}\" word for word", 1.0)
    if best_partial:
        return (best_partial,
                f"contains part of \"{best_partial}\" in order - the points for a "
                f"whole phrase are not earned", 0.55)
    return "", "contains no harvested search phrase", 0.0


def score(title: str, config, *, phrases: list[str] | None = None,
          footage_words: list[str] | None = None) -> dict:
    """Score one title. Returns the number and the working, criterion by criterion."""
    title = (title or "").strip()
    low, high = _band(config)
    parts: list[dict] = []

    def part(name: str, points: float, of: int, note: str) -> None:
        parts.append({"part": name, "points": round(points, 1), "of": of, "note": note})

    if not title:
        return {"title": "", "minutes": 0, "parts": [
            {"part": "search phrase", "points": 0, "of": 35, "note": "there is no title"}],
            "total": 0, "band": [low, high], "min": SCORE_MIN, "pass": False,
            "verdict": "nothing to score"}

    # ------------------------------------------------ harvested search phrase, 35
    hit, why, how_much = phrase_hit(title, phrases or [])
    part("search phrase", 35 * how_much, 35, why)

    # -------------------------------------------------------------- length, 15
    length = len(title)
    if low <= length <= high:
        part("length", 15, 15, f"{length} characters, inside the band {low}-{high} "
                               f"(the plan's 40-60 is an English width rule)")
    elif length < low:
        part("length", max(0.0, 15 - (low - length) * 1.5), 15,
             f"{length} characters, {low - length} under the band {low}-{high}")
    else:
        part("length", max(0.0, 15 - (length - high) * 1.0), 15,
             f"{length} characters, {length - high} over the band {low}-{high} - "
             f"the feed cuts it off")

    # ------------------------------------------------ question or contrarian, 15
    question = [w for w in QUESTION_WORDS if w in title]
    contrarian = [w for w in CONTRARIAN_WORDS if w in title]
    if question:
        part("question or contrarian", 15, 15, f"a question: {question[0]}")
    elif contrarian:
        part("question or contrarian", 15, 15, f"pushes back: {contrarian[0]}")
    else:
        part("question or contrarian", 0, 15, "neither a question nor a claim that pushes back")

    # ---------------------------------------------------------- emotion word, 10
    feelings = [w for w in EMOTION_WORDS if w in title]
    part("emotion word", 10 if feelings else 0, 10,
         f"carries a feeling: {', '.join(feelings[:3])}" if feelings
         else "no word that carries a feeling")

    # --------------------------------------------------------- no footage nouns, 10
    nouns = [n for n in (footage_words or []) if n and n in title]
    part("no footage nouns", 0 if nouns else 10, 10,
         f"names the footage: {', '.join(nouns[:3])} - a headline is about the "
         f"subject, not the shot" if nouns else "names the subject, not the shot")

    # ----------------------------------------------------------------- names, 10
    name_hits = textscan.names({"title": title})
    latin = [h["found"] for h in name_hits if h["kind"] == "latin script"]
    forbidden = [h["found"] for h in name_hits if h["kind"] == "forbidden name"]
    if forbidden:
        part("no names", 0, 10, f"a forbidden name: {', '.join(forbidden[:2])}")
    elif latin:
        part("no names", 0, 10, f"Latin script on screen: {', '.join(latin[:3])}")
    else:
        part("no names", 10, 10, "no names, no Latin script")

    # ------------------------------------------------------- banned phrases, 5
    banned = [p for p in BANNED_PHRASES if p.lower() in title.lower()]
    banned += [h["found"] for h in textscan.leaks({"title": title})][:3]
    if banned:
        part("banned phrases absent", 0, 5, "banned: " + ", ".join(sorted(set(banned))[:3]))
    else:
        part("banned phrases absent", 5, 5, "none of the banned framing is present")

    total = sum(p["points"] for p in parts)
    return {
        "title": title,
        "characters": length,
        "band": [low, high],
        "phrases_used": phrases or [],
        "matched_phrase": hit,
        "parts": parts,
        "total": round(total),
        "min": SCORE_MIN,
        "target": GENERATOR_TARGET,
        "pass": total >= SCORE_MIN,
        "at_target": total >= GENERATOR_TARGET,
        "verdict": "passes" if total >= SCORE_MIN else "below the gate",
    }


def lines(scored: dict) -> list[str]:
    """The score, one criterion per line - for the console and the report."""
    out = [f"{scored['total']:3}/100  {scored['title']}"]
    for row in scored["parts"]:
        out.append(f"        {row['part']:24} {row['points']:5.1f}/{row['of']:<3} {row['note']}")
    return out
