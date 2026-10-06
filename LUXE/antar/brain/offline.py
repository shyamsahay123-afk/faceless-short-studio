"""
LUXE - Offline topic pool - English luxury quotes only

Basic English for everyone to understand easily.
No Hindi. Center placed, luxury minimal.

Hand-verified, real Instagram trending quotes.
"""

from __future__ import annotations

from .topics import Topic

OFFLINE_TOPICS: list[dict] = [
    {
        "topic_en": "Quiet luxury mindset",
        "question_en": "How to look rich without trying?",
        "search_phrase_en": "quiet luxury quotes",
        "title_en": "Quiet luxury is not loud",
        "mechanism_en": "Old money doesn't chase, it attracts",
        "hook_angle": "luxury",
        "structure": "quote-only",
    },
    {
        "topic_en": "Main character energy",
        "question_en": "How to be main character?",
        "search_phrase_en": "main character energy",
        "title_en": "Main character energy",
        "mechanism_en": "You are the main character, not extra",
        "hook_angle": "main-character",
        "structure": "bold-statement",
    },
    {
        "topic_en": "Old money doesn't chase",
        "question_en": "Why old money is different?",
        "search_phrase_en": "old money quotes",
        "title_en": "Old money doesn't chase",
        "mechanism_en": "Chasing is for new money",
        "hook_angle": "luxury",
        "structure": "quote-only",
    },
    {
        "topic_en": "Less is more",
        "question_en": "Why minimal is luxury?",
        "search_phrase_en": "less is more quote",
        "title_en": "Less is more",
        "mechanism_en": "Minimalism is the ultimate luxury",
        "hook_angle": "soft",
        "structure": "quote-only",
    },
    {
        "topic_en": "Self respect over attention",
        "question_en": "How to keep self respect?",
        "search_phrase_en": "self respect quotes",
        "title_en": "Self respect over attention",
        "mechanism_en": "Attention is cheap, respect is expensive",
        "hook_angle": "bold",
        "structure": "bold-statement",
    },
    {
        "topic_en": "Not everyone gets access",
        "question_en": "Why set boundaries?",
        "search_phrase_en": "boundaries quotes",
        "title_en": "Not everyone gets access",
        "mechanism_en": "Privacy is luxury",
        "hook_angle": "bold",
        "structure": "quote+clip",
    },
    {
        "topic_en": "Elegance is silent",
        "question_en": "What is true elegance?",
        "search_phrase_en": "elegance quotes",
        "title_en": "Elegance is silent",
        "mechanism_en": "Loud is cheap, silent is expensive",
        "hook_angle": "luxury",
        "structure": "quote-only",
    },
    {
        "topic_en": "Main character doesn't compete",
        "question_en": "Why not compete?",
        "search_phrase_en": "main character quotes",
        "title_en": "Main character doesn't compete",
        "mechanism_en": "Main character creates own lane",
        "hook_angle": "main-character",
        "structure": "bold-statement",
    },
    {
        "topic_en": "Old money is quiet",
        "question_en": "How old money behaves?",
        "search_phrase_en": "old money mindset",
        "title_en": "Old money is quiet",
        "mechanism_en": "Quiet moves, loud results",
        "hook_angle": "luxury",
        "structure": "quote-only",
    },
    {
        "topic_en": "You are the standard",
        "question_en": "How to be standard?",
        "search_phrase_en": "self worth quotes",
        "title_en": "You are the standard",
        "mechanism_en": "Stop lowering standard for anyone",
        "hook_angle": "bold",
        "structure": "bold-statement",
    },
]


def as_topics():
    from .topics import Topic
    topics = []
    for t in OFFLINE_TOPICS:
        # Adapt to Topic class that expects Hindi fields but we use English
        # Create with both hi and en for compatibility
        topics.append(
            Topic(
                topic_hi=t["topic_en"],
                question_hi=t["question_en"],
                search_phrase_hi=t["search_phrase_en"],
                title_hi=t["title_en"],
                mechanism_hi=t["mechanism_en"],
                hook_angle=t["hook_angle"],
                structure=t["structure"],
            )
        )
    return topics
