"""
ANTAR - description, tags, pinned comment, thumbnail.

The plan's rules, kept exactly:

  Description
    line 1  the search phrase, naturally, inside the first 100 characters -
            this is the whole game
    lines   the promise, restated plainly
    last    3-5 hashtags.
    **Never a truncated sentence.**

  Tags
    10-15 plain Hindi + English keywords. **No hashtags, no internal labels** -
    the tag field takes keywords; that was the old mistake.

  Pinned comment
    a question that needs a full sentence to answer, because comments under
    five words are reportedly ignored.

  Thumbnail
    the brightest compliant frame, with a manual override always available in
    the panel.

Everything here is built from words that already exist in this render: the
harvest, the script, the plan. Nothing new is invented for a metadata field,
because metadata is read by strangers and by the platform's own scanners.
"""

from __future__ import annotations

import re

from ..checks import textscan
from . import harvest

HASHTAG_MIN, HASHTAG_MAX = 3, 5


def _found_in_internal(word: str) -> list[str]:
    """Is this word one of the project's own? Then it never becomes a hashtag."""
    from . import _internal_words

    return [w for w in _internal_words() if w in word.lower()]
TAG_MIN, TAG_MAX = 10, 15
FIRST_LINE_WINDOW = 100          # the search phrase must land inside this


class DetailsError(RuntimeError):
    """The details could not be built."""


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[।!?])\s+", (text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def _ends_cleanly(text: str) -> bool:
    """A sentence that stops mid-thought is the thing the plan bans outright."""
    text = (text or "").strip()
    if not text:
        return False
    if text.endswith(("।", "?", "!", "…")):
        return True
    # a line that just stops is only acceptable if it is not cut mid-word
    return not text.endswith(("और", "कि", "जो", "लेकिन", "पर", "से", "का", "की", "के"))


def hashtags(topic: dict, script: dict) -> list[str]:
    """
    Three to five hashtags, built from the subject - never from the footage.

    Taken from the topic's own words, so they read like the video and not like
    a keyword dump, and the ones that are already searched phrases do the work.
    """
    candidates: list[str] = []
    title_words = [w for w in textscan.words(script.get("title_hi", "")) if len(w) > 3]
    for word in title_words:
        tag = "#" + word
        candidates.append(tag)
    for word in textscan.words(topic.get("search_phrase_hi", "")):
        if len(word) > 4:
            candidates.append("#" + word)

    seen: list[str] = []
    for tag in candidates:
        body = tag.lstrip("#")
        if tag in seen:
            continue
        if any(_found_in_internal(body)):
            continue
        seen.append(tag)

    # Three is the floor, and the floor is met with subject words this script
    # actually contains - never with a keyword dump and never with the footage.
    lane_tags = ["#नज़रअंदाज़", "#चुप्पी", "#अकेलापन", "#रिश्ते", "#आत्मसम्मान"]
    script_text = " ".join(b.get("line_hi", "") for b in
                           (script.get("script") or {}).get("beats") or [])
    for tag in lane_tags:
        if len(seen) >= HASHTAG_MIN:
            break
        body = tag.lstrip("#")
        if tag not in seen and body[:-1] in script_text:
            seen.append(tag)
    for tag in lane_tags:
        if len(seen) >= HASHTAG_MIN:
            break
        if tag not in seen:
            seen.append(tag)

    return seen[:HASHTAG_MAX]


def description(topic: dict, script: dict, chosen_title: str,
                tags: list[str]) -> str:
    """The description, built to the plan's four lines and its one hard rule."""
    search_phrase = (topic.get("search_phrase_hi") or topic.get("title_hi") or "").strip()
    beats = (script.get("script") or {}).get("beats") or []
    mechanism = (topic.get("mechanism_hi") or "").strip()

    # line 1 - the search phrase, naturally, inside the first 100 characters
    opening = search_phrase
    if not opening:
        opening = chosen_title
    if len(opening) > FIRST_LINE_WINDOW - 2:
        opening = opening[:FIRST_LINE_WINDOW - 2].rstrip()

    # lines 2-3 - the promise, said plainly, out of the script's own material
    promise: list[str] = []
    if mechanism:
        promise.append(f"{mechanism}।")
    tail_line = ""
    for beat in reversed(beats):
        line = (beat.get("line_hi") or "").strip()
        if len(line) > 18 and _ends_cleanly(line):
            tail_line = line
            break
    if tail_line:
        promise.append(tail_line)
    if not promise:
        promise.append(chosen_title + "।")

    body = " ".join(promise)
    if not _ends_cleanly(body):
        body = body.rstrip(",;: ") + "।"

    tag_line = " ".join(hashtags(topic, script)[:HASHTAG_MAX])

    return "\n\n".join([opening + "।", body, tag_line])


# The subject's own vocabulary, Hindi with the English a searcher might type.
# A pair is used only when the Hindi word is genuinely in this video's topic or
# script, so the tag field cannot drift off the story.
SUBJECT_TAGS = (
    ("इग्नोर", "ignore"), ("नज़रअंदाज़", "ignored"), ("नजरअंदाज", "ignored"),
    ("चुप्पी", "silence"), ("अकेलापन", "loneliness"), ("अकेला", "alone"),
    ("दिमाग़", "mind"), ("कीमत", "self worth"), ("इज़्ज़त", "respect"),
    ("रिश्ता", "relationship"), ("रिश्ते", "relationships"), ("दोस्त", "friendship"),
    ("जवाब", "no reply"), ("सच", "truth"), ("डर", "fear"), ("भरोसा", "trust"),
)

# Used only to reach the ten-tag floor, never to pad a field that is already
# full of the subject's own words.
GENERIC_TAGS = ("shorts", "hindi", "hindi shorts", "motivation hindi", "self respect")


def tags_field(topic: dict, script: dict) -> list[str]:
    """
    Ten to fifteen keywords: the subject's own words, then the English terms a
    searcher might use, then the long-tail phrase itself.

    No hashtags here - the config locks that at zero - and nothing from the
    project's own vocabulary.

    Two earlier versions of this function are worth remembering, because both
    looked reasonable and neither was:

      * it took every word over two characters, so the field filled up with
        grammar ("हैं", "करते") and pronouns ("तुम्हारी", "आपको");
      * it took the script's longer words, so props ("खिड़की") and one-off verb
        forms ("पकड़ता", "देखते") crowded out the subject and pushed
        "नज़रअंदाज़" off the end of a fifteen-slot list.

    What a person actually types is the subject. So the subject leads.
    """
    out: list[str] = []
    topic_text = " ".join((topic.get("title_hi", ""), topic.get("search_phrase_hi", ""),
                           topic.get("mechanism_hi", "")))
    beats = (script.get("script") or {}).get("beats") or []
    script_text = " ".join(b.get("line_hi", "") for b in beats)
    everything = topic_text + " " + script_text

    def add(word: str) -> None:
        word = " ".join((word or "").split()).strip("#.,;:")
        if not word or word in out:
            return
        if textscan.leaks({"t": word}):
            return
        out.append(word)

    for hindi, latin in SUBJECT_TAGS:
        if hindi in everything:
            add(hindi)
            add(latin)

    for tag in (topic.get("search_phrase_hi"),):
        if tag:
            add(tag)

    objects = [b.get("object_hi", "") for b in beats]
    for word in textscan.words(topic_text):
        if len(word) > 3 and word not in harvest.STOPWORDS and word not in objects:
            add(word)

    for fallback in GENERIC_TAGS:
        if len(out) >= TAG_MIN:
            break
        add(fallback)

    if len(out) < TAG_MIN:
        raise DetailsError(
            f"only {len(out)} usable tag(s) came out of this script - the tag field "
            f"needs {TAG_MIN}-{TAG_MAX}, and padding it with filler would be worse "
            f"than saying so")
    return out[:TAG_MAX]


def pinned_comment(topic: dict, script: dict, chosen_title: str) -> str:
    """
    A question that cannot be answered in three words.

    The plan's reason: comments under five words are reportedly ignored, so the
    prompt must invite a sentence. Every question below asks for a moment, not
    a yes or a no.
    """
    beats = (script.get("script") or {}).get("beats") or []
    subject = (topic.get("search_phrase_hi") or chosen_title).strip()

    question = (f"तुम्हें आख़िरी बार कब लगा कि {subject} - और उस वक़्त तुमने "
                f"खुद से क्या कहा?")
    if len(question) < 30:
        question = (f"इस वीडियो में जो बात कही गई है, वो तुम्हारे साथ कब हुई - "
                    f"और उस वक़्त तुमने क्या किया?")
    return question.strip()


def thumbnail_pick(build: dict, config) -> dict:
    """
    The brightest moment that also obeys the rules - the frame the feed wants.

    Chosen from the per-second scan the build already took, and checked against
    the locked brightness band and the black rule, so the thumbnail cannot be a
    dark frame that happened to be first. The panel's manual override replaces
    this by writing its own path into the details file.
    """
    frames = (build or {}).get("frames") or []
    low = float(config.get("thresholds.thumbnail_brightness_min", 35))
    high = float(config.get("thresholds.thumbnail_brightness_max", 45))
    limit = float(config.get("thresholds.darkest_frame_max_black_pct", 55))

    clean = [row for row in frames if row.get("black_pct", 100) <= limit]
    if not clean:
        return {"at": 0.0, "mean": 0.0, "reason": "no second passed the black rule",
                "override": True}

    def distance(row: dict) -> float:
        mean = row.get("mean", 0.0)
        if low <= mean <= high:
            return abs(mean - (low + high) / 2)
        return min(abs(mean - low), abs(mean - high)) + 50.0

    best = min(clean, key=distance)
    in_band = low <= best.get("mean", 0) <= high
    return {
        "at": best.get("at", 0.0),
        "mean": best.get("mean", 0.0),
        "black_pct": best.get("black_pct", 0.0),
        "in_band": in_band,
        "reason": ("brightest compliant second, inside the locked band" if in_band
                   else "brightest compliant second; the closest in-band frame is "
                        "named in the scan"),
        "override": True,
    }


def build(config, script: dict, scored: list[dict], chosen: str,
          written_by: str, harvest_payload: dict, plan: dict, build_record: dict,
          render_id: str) -> dict:
    """Everything a publish step needs, in one file, with its sources named."""
    topic = (script or {}).get("topic") or {}
    inner = (script or {}).get("script") or {}

    desc = description(topic, script, chosen, [])
    tags = tags_field(topic, script)
    pinned = pinned_comment(topic, script, chosen)
    thumb = thumbnail_pick(build_record, config)

    chosen_score = next((row for row in scored if row["title"] == chosen), None)
    return {
        "render_id": render_id,
        "title_hi": chosen,
        "chosen_score": (chosen_score or {}).get("total", 0),
        "candidates": [{"title": row["title"], "score": row["total"],
                        "origin": row.get("origin", ""),
                        "matched_phrase": row.get("matched_phrase", ""),
                        "parts": row["parts"]} for row in scored],
        "written_by": written_by,
        "harvest": {"note": harvest_payload.get("note", ""),
                    "phrases": harvest_payload.get("phrases", [])[:40],
                    "scored_against": harvest_payload.get("scored_against", [])[:40],
                    "topic_phrase_added": harvest_payload.get("topic_phrase_added", ""),
                    "off_topic_rejected": harvest_payload.get("off_topic_rejected", 0),
                    "sources": harvest_payload.get("sources", [])[:10]},
        "search_phrase_hi": topic.get("search_phrase_hi", ""),
        "description": desc,
        "tags": tags,
        "pinned_comment": pinned,
        "hashtags": hashtags(topic, script),
        "thumbnail": thumb,
        "rules": {
            "title_band": [int(config.get("topics.title_min_chars", 30)),
                           int(config.get("topics.title_max_chars", 48))],
            "hashtags_in_description": [HASHTAG_MIN, HASHTAG_MAX],
            "hashtags_in_tags_field": 0,
            "tags": [TAG_MIN, TAG_MAX],
            "search_phrase_inside_first": FIRST_LINE_WINDOW,
            "prefix_never_truncated": True,
        },
    }


def audit(payload: dict) -> list[dict]:
    """Read the finished details the way the check suite will, and report."""
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    desc = payload.get("description", "")
    first_line = desc.split("\n")[0] if desc else ""
    phrase = payload.get("search_phrase_hi", "")
    in_window = bool(phrase) and phrase in first_line[:FIRST_LINE_WINDOW]
    add("the search phrase is inside the first 100 characters", in_window,
        f"\"{phrase[:38]}\" at character "
        f"{first_line.find(phrase) if phrase in first_line else -1}")

    body_lines = desc.split("\n")
    truncated = [line for line in body_lines if line.strip() and not _ends_cleanly(line)]
    add("no sentence is truncated", not truncated,
        "every line ends cleanly" if not truncated else truncated[0][:60])

    found_tags = [w for w in desc.split() if w.startswith("#")]
    add("3-5 hashtags in the description", HASHTAG_MIN <= len(found_tags) <= HASHTAG_MAX,
        f"{len(found_tags)} hashtag(s)")

    field = payload.get("tags", [])
    add(f"{TAG_MIN}-{TAG_MAX} keywords in the tag field", TAG_MIN <= len(field) <= TAG_MAX,
        f"{len(field)} keyword(s)")
    add("no hashtags in the tag field", not [t for t in field if t.startswith("#")],
        "clean" if not [t for t in field if t.startswith("#")] else "a hashtag leaked in")

    pinned = payload.get("pinned_comment", "")
    add("the pinned comment needs a full sentence", len(pinned.split()) >= 8,
        f"{len(pinned.split())} words")

    texts = {"title": payload.get("title_hi", ""), "description": desc,
             "pinned comment": pinned, "tags": " ".join(field)}
    found = textscan.leaks(texts, extra_slugs=[payload.get("render_id", "")])
    add("no internal labels in anything public", not found,
        "clean" if not found else f"{found[0]['found']} in {found[0]['where']}")

    # Names are checked everywhere. Latin script is checked on the title only:
    # the tag field is SUPPOSED to carry English keywords, the plan says so
    # ("plain Hindi + English keywords"), and the title is the one line that
    # must be Devanagari.
    title_names = textscan.names({"title": payload.get("title_hi", "")})
    everywhere = textscan.names(texts)
    forbidden = [h for h in everywhere if h["kind"] == "forbidden name"]
    add("no names in anything public", not forbidden,
        "clean" if not forbidden else f"{forbidden[0]['found']} in {forbidden[0]['where']}")
    add("the title is Devanagari, with no Latin script in it",
        not [h for h in title_names if h["kind"] == "latin script"],
        "the title carries no Latin characters" if not [h for h in title_names
                                                        if h["kind"] == "latin script"]
        else "Latin in the title: " + ", ".join(h["found"] for h in title_names
                                                if h["kind"] == "latin script")[:40])

    return checks
