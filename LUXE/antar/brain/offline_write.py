"""
LUXE - Offline script writer - English luxury quotes only

Basic English, 3-8 words, centered, no voice.
"""

from __future__ import annotations

from . import audit
from .topics import Topic
from .writer import Draft, Result


OFFLINE_SCRIPT_FLOOR = 3
OFFLINE_SCRIPT_CEILING = 10


def _make_script(title: str, body_lines: list[str], question: str, clip_urls: list[str], tags: list[str] | None = None) -> dict:
    beats = []
    for i, text in enumerate(body_lines):
        beats.append({
            "line_en": text.strip(),
            "line_hi": text.strip(),
            "object_hi": "text",
            "object_en": "text",
            "role": "quote",
            "kind": "quote",
            "pause_after_ms": 0,
        })
    title_short = title if len(title) <= 30 else title[:30].rsplit(" ", 1)[0]
    return {
        "title_en": title,
        "title_hi": title,
        "title_short_en": title_short,
        "title_short_hi": title_short,
        "closing_echo": beats[-1]["line_en"] if beats else "",
        "peak_line": 1,
        "beats": beats,
        "question_en": question,
        "question_hi": question,
        "tags": tags or ["quiet luxury", "main character", "old money"],
        "hashtags": [],
    }


TEMPLATES = [
    {"title": "Quiet luxury is not loud", "lines": ["Quiet luxury is not loud"], "question": "How to look rich without trying?", "clips": [], "tags": ["quiet luxury", "old money"]},
    {"title": "Main character energy", "lines": ["Main character energy"], "question": "How to be main character?", "clips": [], "tags": ["main character"]},
    {"title": "Old money doesn't chase", "lines": ["Old money doesn't chase"], "question": "Why old money different?", "clips": [], "tags": ["old money"]},
    {"title": "Less is more", "lines": ["Less is more"], "question": "Why minimal is luxury?", "clips": [], "tags": ["minimal"]},
    {"title": "You are the standard", "lines": ["You are the standard"], "question": "How to be standard?", "clips": [], "tags": ["self respect"]},
    {"title": "Elegance is silent", "lines": ["Elegance is silent"], "question": "What is elegance?", "clips": [], "tags": ["elegance"]},
]


def write_offline(topic: Topic) -> Result:
    title = getattr(topic, 'title_en', None) or getattr(topic, 'title_hi', 'Quiet luxury is not loud')
    template = TEMPLATES[0]
    for t in TEMPLATES:
        if t["title"].lower() in title.lower() or title.lower() in t["title"].lower():
            template = t
            break
    
    script = _make_script(template["title"], template["lines"], template["question"], template["clips"], template["tags"])
    report = audit.audit_script(script)
    draft = Draft(script=script, report=report, model="offline", service="offline", attempt=1)
    result = Result(script=script, report=report)
    result.model = "offline"
    result.service = "offline"
    result.attempts.append(f"offline/template: {report.words} words, score {report.score()}")
    return result
