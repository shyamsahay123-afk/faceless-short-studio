"""
ANTAR - the object dictionary.

Why this exists, in one measured sentence:

    A script sentence cannot be searched. Of twelve results for
    "you notice your confidence shrinking", one was usable footage.
    For "empty chair", twelve of twelve were clean.

So the writer must name an object in every line, and the picture engine
searches the OBJECT, never the sentence.

Each entry is a Hindi trigger word and the English phrase that returns clean
footage on a stock library. The English side is deliberately concrete:
"empty chair" returns a chair; "loneliness" returns people with faces.
"""

from __future__ import annotations

import re

# no faces. silhouettes, hands, backs of heads, empty rooms and objects only.
OBJECTS: dict[str, str] = {
    # -- seating and rooms
    "कुर्सी": "empty chair",
    "मेज़": "empty table",
    "सोफ़ा": "empty sofa",
    "कमरा": "empty room",
    "दीवार": "plain wall shadow",
    "कोना": "empty corner",
    "फ़र्श": "bare floorboards",
    "सीढ़ी": "empty staircase",
    "गलियारा": "empty corridor",
    "बरामदा": "empty balcony",
    "खिड़की": "window at night",
    "दरवाज़ा": "closed door",
    "पर्दा": "curtain moving in the wind",
    "लिफ़्ट": "elevator doors",
    "बिस्तर": "empty bed",
    "तकिया": "pillow on a bed",
    "चादर": "crumpled bedsheet",

    # -- small objects
    "फ़ोन": "smartphone on table",
    "मोबाइल": "smartphone screen dark",
    "स्क्रीन": "dark screen close up",
    "मैसेज": "phone notification screen",
    "कॉफ़ी": "mug on table",
    "चाय": "cup of tea on table",
    "मग": "coffee mug on table",
    "गिलास": "glass of water on table",
    "पानी": "water surface ripples",
    "कप": "single cup on saucer",
    "प्लेट": "empty plate on table",
    "चाकू": "knife on a board",
    "चाबी": "keys on a table",
    "घड़ी": "clock on wall",
    "समय": "wall clock ticking",
    "दीया": "candle flame in the dark",
    "मोमबत्ती": "candle burning down",
    "धुआँ": "smoke drifting in the dark",
    "रोशनी": "single lamp in a dark room",
    "बल्ब": "bare light bulb",
    "छाया": "shadow on a wall",
    "आईना": "empty mirror",
    "किताब": "closed book on table",
    "कागज़": "blank paper on a desk",
    "कलम": "pen on paper",
    "कपड़े": "folded clothes",
    "जूते": "shoes by a door",
    "बैग": "bag left on the floor",
    "बोतल": "single bottle on a table",
    "पौधा": "plant by a window",
    "पत्ते": "leaves moving",
    "फूल": "single flower wilting",
    "धूल": "dust in a beam of light",
    "बारिश": "rain on a window",
    "पानी की बूँद": "water drops on glass",
    "बर्फ़": "frost forming on glass",
    "कोहरा": "fog over a road",
    "आसमान": "grey sky clouds",
    "सड़क": "empty road at night",
    "रेल": "train window passing",
    "पटरी": "railway tracks receding",
    "पुल": "empty bridge",
    "दरिया": "river at dusk",
    "समुद्र": "sea waves at night",
    "आग": "fire burning down",
    "लकड़ी": "wood grain close up",
    "काँच": "cracked glass",
    "तार": "hanging wire",
    "बादल": "clouds moving fast",
    "सायरन": "warning light flashing",
    "सीट": "empty bus seat",
    "गाड़ी": "car headlights in rain",
    "पहिय़ा": "wheel turning",
}

# references to the other person that are allowed. anything else is a name.
ALLOWED_REFERENCES = {
    "तुम", "तुम्हारा", "तुम्हारी", "तुम्हारे", "तुम्हें", "तुमसे", "तुमने",
    "वो", "वह", "उसने", "उसका", "उसकी", "उसके", "उसे", "उन्होंने", "उनका",
    "उनकी", "उनके", "उन्हें", "मैं", "मुझे", "मेरा", "मेरी", "मेरे", "हम",
    "आप",  # flagged separately as a style breach, not as a name
}

# a small list of names that must never appear. matched on word boundaries.
BANNED_NAMES = {
    # latin, in case the model slips into English
    "carlos", "riya", "priya", "rahul", "arjun", "aditi", "sara", "sam",
    "john", "mary", "alex", "raj", "neha", "vikram", "kabir", "zoya",
    # devanagari
    "कार्लोस", "रिया", "प्रिया", "राहुल", "अर्जुन", "अदिति", "सारा", "राज",
    "नेहा", "विक्रम", "कबीर", "ज़ोया", "जॉन", "मैरी", "सैम", "एलेक्स",
}


def resolve(line: str, hint: str = "") -> tuple[str, str] | None:
    """
    Find the filmable object in a line.

    Returns (search_query, matched_word) - the English query to send to the
    stock library, and the Hindi word that triggered it. None if the line
    contains no object at all, which is itself a finding: that beat will need
    a text card, and the writer should be sent back to fix it.

    `hint` is the object the writer promised in its plan, checked first.
    """
    if hint and hint in OBJECTS:
        return OBJECTS[hint], hint
    if hint:
        for key, query in OBJECTS.items():
            if hint in key or key in hint:
                return query, key

    best: tuple[str, str] | None = None
    for key, query in OBJECTS.items():
        if key in line:
            # prefer the longest match, so "मोबाइल" beats a stray substring
            if best is None or len(key) > len(best[1]):
                best = (query, key)
    return best


def objects_in(line: str) -> list[str]:
    return [key for key in OBJECTS if key in line]


def find_banned_names(text: str) -> list[str]:
    """Names that must never appear, in either script."""
    found: list[str] = []
    lowered = text.lower()
    for name in BANNED_NAMES:
        if name.isascii():
            if re.search(rf"\b{re.escape(name)}\b", lowered):
                found.append(name)
        elif name in text:
            found.append(name)
    return found


def has_apa(text: str) -> bool:
    """आप creates distance. This niche needs तुम."""
    return bool(re.search(r"आप", text))


def count_tum(text: str) -> int:
    return len(re.findall(r"तुम", text))
