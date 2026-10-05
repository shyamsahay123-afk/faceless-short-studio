"""
ANTAR - the topic engine.

Lane B, in one sentence:

    A practical question about being overlooked, answered with a mechanism the
    viewer did not know, delivered intimately.

The engine generates candidates, then filters them with real evidence:

  * the search box test, against live autocomplete
  * a numeric lane test - banned words, footage nouns, question shape, length
  * a name check

Anything that survives both is kept. Anything that fails is dropped and the
reason is printed, so the reason the funnel narrowed is visible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .. import log
from . import models, objects, prompts, searchbox
from .providers import Brain, extract_json

# words that mean the title is describing a picture, not a subject
FOOTAGE_NOUNS = ("बर्फ़", "धुआँ", "खिड़की", "कोहरा", "बारिश", "लिफ़्ट", "कुर्सी",
                 "मोमबत्ती", "आईना", "दरी", "पत्ते", "समुद्र", "नदी", "चाँद")

# words that promise nothing actionable
EMPTY_PROMISES = ("रहस्य", "जादू", "चौंकाने", "अविश्वसनीय", "गुप्त सच")

# seeds for the vocabulary harvest
LANE_SEEDS = ("लोग मुझे इग्नोर", "इग्नोर होने", "कोई जवाब नहीं देता",
              "नज़रअंदाज़", "बात नहीं सुनते", "शर्मीला")


@dataclass
class Topic:
    topic_hi: str
    question_hi: str
    search_phrase_hi: str
    title_hi: str
    mechanism_hi: str
    hook_angle: str
    structure: str
    search: dict = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    title_length: int = 0
    search_phrases_hi: list = field(default_factory=list)
    search_phrases_tested: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def signal(self) -> str:
        return self.search.get("signal", "none")

    @property
    def detail(self) -> str:
        return (f"[{self.signal:7}] {self.title_hi}   "
                f"({self.title_length} chars, {self.hook_angle})")


# ---------------------------------------------------------------- the lane test

def lane_test(topic: Topic, min_chars: int, max_chars: int) -> list[str]:
    """Numeric checks. Returns the list of failures, empty means it passed."""
    failures: list[str] = []
    title = topic.title_hi or ""
    topic.title_length = len(title)

    if not title.strip():
        failures.append("no title")
    if len(title) < min_chars:
        failures.append(f"title {len(title)} chars, below {min_chars}")
    if len(title) > max_chars:
        failures.append(f"title {len(title)} chars, above {max_chars}")

    for word in FOOTAGE_NOUNS:
        if word in title:
            failures.append(f"title names footage ('{word}') - it belongs in the body, not the headline")
            break

    for word in EMPTY_PROMISES:
        if word in title:
            failures.append(f"title promises nothing ('{word}')")
            break

    banned = [word for word in ("स्टोइक", "डार्क साइकोलॉजी", "डार्क साइकोलॉजि", "अल्फा",
                                "सिग्मा", "मोटिवेशन", "हसल", "माइंडसेट", "मैनिपुलेशन")
              if word in title or word in (topic.topic_hi or "")]
    if banned:
        failures.append(f"banned framing: {', '.join(banned)}")

    names = objects.find_banned_names(title + " " + (topic.topic_hi or ""))
    if names:
        failures.append(f"name in topic: {', '.join(names)}")

    if not (topic.mechanism_hi or "").strip():
        failures.append("no mechanism - the video would have no answer")

    if not re.search(r"[?]|क्यों|कैसे|कब|क्या", title):
        failures.append("title is not a question or a claim someone would search")

    return failures


# ---------------------------------------------------------------- generation

def generate(brain: Brain, count: int, config, ledger_probe: bool = True) -> tuple[list[Topic], str]:
    """
    Ask the strongest models for topics, then filter.

    Tries models strongest first and stops at the first model that returns a
    usable list. Every model is reported - nothing is chosen silently.
    """
    cfg_topics = config.get("topics", {}) or {}
    prefer = config.get("brain.prefer_models", []) or []
    ladder = models.ladder(brain, prefer)
    if not ladder:
        return [], "no models available - every key down or unreachable"

    min_chars = int(cfg_topics.get("title_min_chars", 40))
    max_chars = int(cfg_topics.get("title_max_chars", 60))
    prompt = prompts.TOPIC_USER.format(count=count)

    attempts: list[str] = []
    for candidate in ladder[:6]:
        ok, text, note = brain.call(
            prompt, candidate.model, candidate.service,
            system=prompts.TOPIC_SYSTEM, temperature=0.9, max_tokens=3000)

        if not ok:
            attempts.append(f"{candidate.model}: {note}")
            log.warn(f"topics: {candidate.service}/{candidate.model} -> {note}")
            if "model unavailable" in note or "404" in note:
                continue
            continue

        parsed = extract_json(text)
        if not parsed or not isinstance(parsed.get("topics"), list):
            attempts.append(f"{candidate.model}: unparseable reply")
            log.warn(f"topics: {candidate.service}/{candidate.model} returned no usable JSON")
            continue

        topics = []
        for raw in parsed["topics"]:
            if not isinstance(raw, dict):
                continue
            topic = Topic(
                topic_hi=str(raw.get("topic_hi", "")).strip(),
                question_hi=str(raw.get("question_hi", "")).strip(),
                search_phrase_hi=str(raw.get("search_phrase_hi", "")).strip(),
                title_hi=str(raw.get("title_hi", "")).strip(),
                mechanism_hi=str(raw.get("mechanism_hi", "")).strip(),
                hook_angle=str(raw.get("hook_angle", "")).strip() or "direct-question",
                structure=str(raw.get("structure", "")).strip() or "problem-mechanism",
                search_phrases_hi=[str(p).strip() for p in (raw.get("search_phrases_hi") or []) if str(p).strip()],
            )
            # if the AI did not honour the new field, seed it with the single phrase
            if not topic.search_phrases_hi and topic.search_phrase_hi:
                topic.search_phrases_hi = [topic.search_phrase_hi]
            topics.append(topic)

        if not topics:
            attempts.append(f"{candidate.model}: empty topic list")
            continue

        log.ok(f"topics: {len(topics)} candidates from {candidate.service}/{candidate.model}")
        return topics, f"{candidate.service}/{candidate.model}" + (
            f" (after {len(attempts)} failed attempt(s): {'; '.join(attempts)})" if attempts else "")

    return [], "every model failed: " + "; ".join(attempts)


# ---------------------------------------------------------------- filtering

def check(topics: list[Topic], config, live: bool = True) -> list[Topic]:
    """
    Run the lane test and the search box test on every candidate.
    Failures are recorded on the topic; nothing is silently dropped.

    If a topic carries `search_phrases_hi` (the AI's suggestions), every
    phrase is tested against YouTube autocomplete; the one with the
    strongest signal wins and becomes `search_phrase_hi`. This stops the
    AI from inventing phrases nobody searches for.
    """
    cfg_topics = config.get("topics", {}) or {}
    min_chars = int(cfg_topics.get("title_min_chars", 30))
    max_chars = int(cfg_topics.get("title_max_chars", 48))
    require = cfg_topics.get("required_signal", "present")

    order = {"none": 0, "thin": 1, "present": 2, "strong": 3}
    need = order.get(require, 2)

    for topic in topics:
        topic.failures = lane_test(topic, min_chars, max_chars)

        if not live:
            continue

        # build the list of phrases to try: AI's suggestions first, then
        # the main one, then the title, then a couple of fallbacks.
        candidates = list(getattr(topic, "search_phrases_hi", []) or [])
        if topic.search_phrase_hi and topic.search_phrase_hi not in candidates:
            candidates.append(topic.search_phrase_hi)
        if topic.title_hi:
            candidates.append(topic.title_hi)
        # dedupe, preserve order
        seen: set[str] = set()
        candidates = [c for c in candidates if c and not (c in seen or seen.add(c))]

        best = {"signal": "none", "suggestions": [], "phrase": ""}
        topic.search_phrases_tested = []
        for phrase in candidates[:5]:  # cap so we don't hammer YouTube
            try:
                result = searchbox.test(phrase)
            except Exception as exc:
                topic.search_phrases_tested.append({"phrase": phrase, "signal": "none",
                                                     "error": str(exc)})
                continue
            topic.search_phrases_tested.append({"phrase": phrase,
                                                 "signal": result.get("signal", "none"),
                                                 "hits": result.get("hits", 0),
                                                 "n_suggestions": len(result.get("suggestions", []))})
            if order.get(result.get("signal", "none"), 0) > order.get(best["signal"], 0):
                best = {"signal": result.get("signal", "none"),
                        "suggestions": result.get("suggestions", []),
                        "phrase": phrase, **result}

        topic.search = best
        # overwrite the AI's phrase with the one YouTube actually knows
        if best["phrase"] and best["signal"] != "none":
            topic.search_phrase_hi = best["phrase"]

        if order.get(topic.signal, 0) < need:
            topic.failures.append(
                f"search box test: every phrase got 0-1 hits, " +
                f"strongest was '{best.get('phrase', '')[:40]}' " +
                f"({len(best.get('suggestions', []))} suggestions, " +
                f"signal {best.get('signal', 'none')}); need {require} - " +
                "this topic has no audience on YouTube yet")

    topics.sort(key=lambda t: (not t.ok, -order.get(t.signal, 0), t.title_length))
    return topics


def harvest(config) -> set[str]:
    """Learn the words real searchers use in this lane."""
    return searchbox.related_vocabulary(list(LANE_SEEDS))
