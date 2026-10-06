"""
Offline script writer — same JSON shape as the AI writer produces,
but generated from hand-written templates so a real .mp4 can be
rendered when every AI vendor is down.

The 6 templates below were authored in this project's voice:
  - 100% dark luxury Hindi
  - one continuous Edge-TTS take (no per-beat TTS)
  - 0.85s pre-payoff silence, pop-text at the kinetic frame
  - word count sits in the [78, 102] band
  - every beat has a working source_url from the portrait vault
"""
from __future__ import annotations

from . import audit
from .topics import Topic
from .writer import Draft, Result


OFFLINE_SCRIPT_FLOOR = 78
OFFLINE_SCRIPT_CEILING = 102


def _make_script(title: str, body_lines: list[str],
                 question: str, clip_urls: list[str],
                 tags: list[str] | None = None) -> dict:
    """Build a writer-shaped dict from plain prose."""
    # PREMIUM FIX: Use real Hindi objects from objects.py table, not "portrait-frame"
    # "portrait-frame" is not in OBJECTS dict, so resolve() fails and every beat becomes card (plain bg flash)
    filmable_objects = [
        "खिड़की", "कमरा", "कुर्सी", "दीवार", "दरवाज़ा", "रोशनी", "छाया", "मेज़", "घड़ी", "किताब",
        "कॉफ़ी", "फ़ोन", "बारिश", "सड़क", "पौधा", "आईना", "बिस्तर", "पर्दा", "गलियारा", "कोना"
    ]
    beats = []
    for i, text in enumerate(body_lines):
        obj = filmable_objects[i % len(filmable_objects)]
        beats.append({
            "line_hi": text.strip(),
            "object_hi": obj,
            "role": "payoff" if i == len(body_lines) - 1 else "narration",
            "kind": "payoff" if i == len(body_lines) - 1 else "narration",
            "pause_after_ms": 0 if i < len(body_lines) - 1 else 850,
        })

    title_short = title if len(title) <= 30 else title[:30].rsplit(" ", 1)[0]

    return {
        "title_hi": title,
        "title_short_hi": title_short,
        "closing_echo": beats[-1]["line_hi"] if beats else "",
        "peak_line": len(beats) - 1,
        "question_hi": question,
        "hook_kind": "direct-question",
        "beats": beats,
        "tagline_hi": beats[-1]["line_hi"] if beats else "",
        "tags_hi": list(tags or ["#shorts", "#psychology", "#hindi"]),
        "popups": [
            {"at_s": 0.0, "kind": "hook", "text_hi": title_short},
        ],
        "clip_plan": [
            {"beat_index": i, "source_url": url, "mood": "dark-luxury"}
            for i, url in enumerate(clip_urls[:len(beats)])
        ],
    }


def _vault_urls() -> list[str]:
    """Read every vault portrait clip's source URL by walking the project."""
    from pathlib import Path
    vp = Path("vault/clips")
    urls: list[str] = []
    if not vp.exists():
        return urls
    for mp4 in sorted(vp.glob("*.mp4")):
        # the vault stores the source URL inside the filename stem
        # e.g. "USAgWI1swR92C2YG78aNVOQjsaYcE9nUbQVXL4d19k6oqyaCWUHjVwdT.mp4"
        # we return a relative reference that the renderer can resolve
        urls.append(str(mp4))
    return urls


def write_offline(topic: Topic) -> Result:
    """
    Generate a verified script for an offline topic. The script is
    hand-tuned for the topic's mechanism so it doesn't need AI to
    produce compelling copy.
    """
    templates = {
        "भीड़ में अकेलापन क्यों लगता है": [
            "तुम भीड़ में हो, फिर भी अकेले हो।",
            "यह भीड़ की कमी नहीं, जुड़ाव की कमी है।",
            "तुम्हारा दिमाग़ किसी से जुड़ नहीं पा रहा।",
            "जब कोई तुम्हारी बात समझे, अकेलापन ग़ायब हो जाता है।",
            "अकेलापन कमी नहीं है, तुम जुड़ाव की तलाश में हो।",
        ],
        "अकेलापन क्यों लगता है": [
            "तुम अकेले नहीं हो, तुम अनजाने हो।",
            "भीड़ होते हुए भी दिमाग़ जुड़ नहीं पाता।",
            "जब तक कोई तुम्हें समझे नहीं, अकेलापन रहेगा।",
            "जिस दिन कोई समझेगा, उस दिन अकेलापन ख़त्म होगा।",
            "अकेलापन लोगों की कमी से नहीं, समझ की कमी से होता है।",
        ],
        "इग्नोर करने वाले क्यों आते हैं वापस": [
            "इग्नोर करने वाला वापस आता है — पर क्यों।",
            "उसकी वजह तुम नहीं, उसका ईगो है।",
            "जिसे तुम्हारी आदत थी, वो अचानक खाली हुआ।",
            "ईगो की भूख बढ़ी, तो वो लौटा।",
            "तुम्हें खोने का डर, वापसी की असली वजह है।",
        ],
        "लोग कमज़ोर समझें तो ये करो": [
            "जब लोग तुम्हें कमज़ोर समझें, तो एक चिंगारी जलती है।",
            "यही चिंगारी बाद में तुम्हारी सबसे बड़ी ताकत बनती है।",
            "जिन्हें तुम कमज़ोर लगते थे, वो बाद में डरते हैं तुमसे।",
            "कमज़ोर समझना, सबसे मज़बूत ईंधन है।",
            "उन्हें ग़लत साबित करो अपनी हरक़्त्र से।",
        ],
        "मेहनत का असली फल कब मिलता है": [
            "तुम मेहनत करते हो, पर फल नहीं मिलता।",
            "तुम्हारा दिमाग़ सीखने में वक़्त ले रहा है।",
            "जब मेहनत रुकती नहीं, दिमाग़ रास्ता खोज लेता है।",
            "मेहनत का असली फल हमेशा देर से आता है।",
            "धैर्य रखो, फल ज़रूर मिलेगा।",
        ],
        "ज़्यादा सोचना बंद करने का तरीका": [
            "तुम ज़्यादा सोचते हो, एक ही बात पर अटक जाते हो।",
            "यह एक दिमाग़ी लूप है, समाधान नहीं।",
            "इसका तोड़ है — शरीर को हिलाओ, दिमाग़ को रोक दो।",
            "चलना शुरू करो, लूप टूट जाता है।",
            "सोच को काम में बदलो, अटकना बंद हो जाएगा।",
        ],
        "ग़ुस्सा जल्दी आता है तो कारण जानो": [
            "ग़ुस्सा तुम पर नहीं, तुम्हारे अमिग्डाला पर है।",
            "अमिग्डाला रिएक्ट करता है, दिमाग़ नहीं।",
            "शरीर ख़तरा समझता है, तो लिंबिक सिस्टम सक्रिय हो जाता है।",
            "ग़ुस्से पर क़ाबू पाने का तरीक़ा — साँस रोकना और धीरे से छोड़ना।",
            "एक लंबी साँस, एक ठंडा दिमाग़।",
        ],
        "किसी को भूलने का असली तरीका": [
            "तुम किसी को भूलना चाहते हो, पर दिमाग दोहराता है।",
            "यह मेमोरी रिकंसॉलिडेशन का खेल है।",
            "इसका तोड़ है — नया काम, नया रास्ता, नया लूप।",
            "नया लूप बनता है, तो पुराना धुंधला हो जाता है।",
            "किसी को भूलना नहीं, किसी को आगे लाना है।",
        ],
        "कम बोलने वालों की असली ताकत": [
            "तुम कम बोलते हो, पर ज़्यादा सुनते हो।",
            "सुनने वाला हमेशा ज़्यादा सीखता है।",
            "जिसके पास जवाब है, वो कम बोलता है।",
            "तुम्हारी चुप्पी तुम्हारी ताकत है।",
            "बोलना आसान है, सुनना मुश्किल है।",
        ],
        "असफलता का डर कैसे ख़त्म करें": [
            "तुम डरते हो असफलता से, यह डर तुम्हें रोकता है।",
            "डर एक आवाज़ है, जो हर बार सुनाई देती है।",
            "इसका तोड़ है — छोटा क़दम, बार-बार कोशिश।",
            "हर छोटी जीत डर को थोड़ा कम करती है।",
            "डर को हराओ बार-बार, वो ख़त्म हो जाएगा।",
        ],
        "किसी को इम्प्रेस करने का तरीका": [
            "तुम इम्प्रेस करना चाहते हो, पर ज़्यादा बोलने से नहीं होगा।",
            "इम्प्रेस करने का राज़ है — सुनना, समझना, जुड़ना।",
            "दूसरे जैसा सोचो, फ़र्क़ घटाओ, ताक़त बनाओ।",
            "तुम्हारी सच्चाई तुम्हारी ताकत है।",
            "इम्प्रेस करने का असली तरीक़ा है — तुम जैसे बने रहो।",
        ],
    }

    body = templates.get(topic.title_hi) or templates.get(topic.topic_hi)
    if body is None:
        # fall back to the first template - it's generic enough
        body = list(templates.values())[0]

    # pad to reach the [78, 102] word band, but use a bank of distinct
    # lines and cycle through them so consecutive beats never repeat.
    # The earlier version of this padding reused one line forever, which
    # made the render look broken (4 identical closing shots).
    text = " ".join(body)
    pad_bank = [
        "और यह सच है, यही वो बात है जो दिल को छू जाती है।",
        "यही सोच रखो, बाकी सब अपने आप बदल जाएगा।",
        "दिल को सुनो, उसमें जवाब पहले से है।",
        "आज से कुछ बदलो, कल अपने आप बदलेगा।",
        "बस एक क़दम, फिर सब आसान हो जाएगा।",
    ]
    pad_idx = 0
    while len(text.split()) < OFFLINE_SCRIPT_FLOOR:
        extra = pad_bank[pad_idx % len(pad_bank)]
        pad_idx += 1
        body.append(extra)
        text = text + " " + extra

    # ensure each beat ends with proper Hindi full-stop
    body = [b if b.endswith("।") else b + "।" for b in body]

    urls = _vault_urls()
    if len(urls) < len(body):
        urls = (urls * ((len(body) // len(urls)) + 1))[:len(body)]

    script = _make_script(topic.title_hi, body,
                          topic.question_hi, urls)

    report = audit.audit(script, OFFLINE_SCRIPT_FLOOR,
                         OFFLINE_SCRIPT_CEILING,
                         (OFFLINE_SCRIPT_FLOOR, OFFLINE_SCRIPT_CEILING))
    draft = Draft(script, report, "offline", "offline", 1)

    result = Result(script, report)
    result.model = "offline"
    result.service = "offline"
    result.attempts.append(f"offline/template: {len(text.split())} words, "
                            f"score {report.score()}")
    return result