"""
LUXE - topic engine - English luxury quotes only

Basic English for everyone to understand easily.
No Hindi. Center placed, luxury minimal.

Generates candidates, then filters with real evidence:
- search box test (optional for Insta)
- lane test: basic English 3-8 words, luxury mood, no Hindi
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .. import log
from . import models, prompts, searchbox
from .providers import Brain, extract_json

# For luxury quotes, no footage nouns ban - quotes are not footage
FOOTAGE_NOUNS = ()

# Empty promises - for luxury, avoid hustle words
EMPTY_PROMISES = ("hustle", "grind", "alpha", "sigma", "hack", "secret trick")

# Seeds for luxury
LANE_SEEDS = ("quiet luxury", "main character energy", "old money", "less is more", "elegance", "self respect")


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
    # English fields for LUXE
    topic_en: str = ""
    question_en: str = ""
    search_phrase_en: str = ""
    title_en: str = ""
    mechanism_en: str = ""

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def signal(self) -> str:
        return self.search.get("signal", "none")

    @property
    def detail(self) -> str:
        title = self.title_en or self.title_hi
        return f"[{self.signal:7}] {title}   ({self.title_length} chars, {self.hook_angle})"


def lane_test(topic: Topic, min_chars: int, max_chars: int) -> list[str]:
    """Numeric checks for LUXE English luxury quotes"""
    failures: list[str] = []
    title = (topic.title_en or topic.title_hi or "").strip()
    topic.title_length = len(title)

    if not title:
        failures.append("no title")
    
    # For LUXE: title 3-40 chars, basic English, 3-8 words
    words = len(title.split())
    if words < 2:
        failures.append(f"title {words} words, below 2 - too short for LUXE")
    if words > 10:
        failures.append(f"title {words} words, above 10 - too long for LUXE, keep 3-8 words")
    
    if len(title) < 3:
        failures.append(f"title {len(title)} chars, below 3")
    if len(title) > 60:
        failures.append(f"title {len(title)} chars, above 60 - keep basic English short")

    # Check for Hindi characters - not allowed in LUXE
    if any('\u0900' <= c <= '\u097F' for c in title):
        failures.append("Hindi characters found - LUXE is English only, basic English")

    # Banned hustle words for quiet luxury
    banned = [w for w in EMPTY_PROMISES if w.lower() in title.lower() or w.lower() in (topic.topic_en or "").lower()]
    if banned:
        failures.append(f"banned framing for quiet luxury: {', '.join(banned)} - quiet luxury is not loud")

    return failures


def check(topics: list[Topic], config, live: bool = True) -> list[Topic]:
    """Check topics with lane test and optional search box"""
    min_chars = 3
    max_chars = 60
    
    for topic in topics:
        topic.failures = lane_test(topic, min_chars, max_chars)
        if live and not topic.failures:
            # Optional search box test for Insta - not blocking
            try:
                phrase = topic.search_phrase_en or topic.search_phrase_hi or topic.title_en or topic.title_hi
                result = searchbox.test(phrase)
                topic.search = result
            except Exception:
                topic.search = {"signal": "none", "suggestions": []}
        else:
            topic.search = {"signal": "offline" if not live else "none", "suggestions": []}
    
    return topics


def generate(brain: Brain, count: int, config) -> tuple[list[Topic], str]:
    """Generate topics via AI brain - English luxury quotes"""
    try:
        from .providers import Brain
        # Use prompts for English luxury
        system = prompts.TOPIC_SYSTEM
        user = prompts.TOPIC_USER.format(count=count)
        
        response = brain.ask(system, user, max_tokens=2000)
        data = extract_json(response)
        raw_topics = data.get("topics", [])
        
        topics = []
        for t in raw_topics:
            # Support both old Hindi fields and new English fields
            topics.append(Topic(
                topic_hi=t.get("topic_en") or t.get("topic_hi", ""),
                question_hi=t.get("question_en") or t.get("question_hi", ""),
                search_phrase_hi=t.get("search_phrase_en") or t.get("search_phrase_hi", ""),
                title_hi=t.get("title_en") or t.get("title_hi", ""),
                mechanism_hi=t.get("mechanism_en") or t.get("mechanism_hi", ""),
                hook_angle=t.get("hook_angle", "luxury"),
                structure=t.get("structure", "quote-only"),
                topic_en=t.get("topic_en", ""),
                question_en=t.get("question_en", ""),
                search_phrase_en=t.get("search_phrase_en", ""),
                title_en=t.get("title_en", ""),
                mechanism_en=t.get("mechanism_en", ""),
            ))
        
        return topics, f"AI generated {len(topics)} English luxury topics"
    except Exception as e:
        log.warn(f"topic generation failed: {e}, using offline pool")
        from .offline import as_topics
        return as_topics(), "offline pool - English luxury quotes"
