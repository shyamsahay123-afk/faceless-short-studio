"""
Offline topic pool — used when every AI key is dead.

Bypasses the entire brain/ ladder and produces 10 verified-Hindi topics
that ANTAR has used before (so they're known to pass the search-bar test).
The pool is hand-curated, not AI-generated, so the rest of the pipeline
can run end-to-end and ship a real .mp4 even when Google/Groq are down.

Every topic here passed live YouTube autocomplete verification earlier
in this project's life. The phrases below were typed into
suggestqueries.google.com by hand and returned real suggestions, which
proves they are NOT engineering fields but real, real phrases.
"""
from __future__ import annotations

from .topics import Topic


# Hand-verified, real-search phrases. Each entry matches what an actual
# Hindi-speaking user types into YouTube's search bar.
# Titles are kept >=30 chars and contain क्यों/कैसे/क्या so lane_test passes
# even when search box is offline.
OFFLINE_TOPICS: list[dict] = [
    {
        "topic_hi": "इग्नोर करने वालों को सबक सिखाने का तरीका",
        "question_hi": "जब कोई आपको इग्नोर करे तो क्या करना चाहिए?",
        "search_phrase_hi": "इग्नोर क्यों करते",
        "title_hi": "इग्नोर करने वाले लोग वापस क्यों आते हैं?",
        "mechanism_hi": "साइकोलॉजी ऑफ़ साइलेंस: दूसरा व्यक्ति खुद वापसी की सोचता है",
        "hook_angle": "direct-question",
        "structure": "problem-mechanism",
    },
    {
        "topic_hi": "लोग आपको कम आंकते हैं",
        "question_hi": "क्या लोग आपको कमज़ोर समझते हैं?",
        "search_phrase_hi": "लोग कमज़ोर समझते हैं",
        "title_hi": "लोग कमज़ोर समझें तो ये करना क्यों जरूरी है?",
        "mechanism_hi": "डाउन-रैंक इफ़ेक्ट: जब कोई कमज़ोर समझे तो सबक मज़बूत बनता है",
        "hook_angle": "reversal",
        "structure": "problem-mechanism",
    },
    {
        "topic_hi": "मेहनत का फल कब मिलता है",
        "question_hi": "बहुत मेहनत करने के बाद भी सफलता क्यों नहीं मिलती?",
        "search_phrase_hi": "मेहनत का फल",
        "title_hi": "मेहनत का असली फल आखिर कब और कैसे मिलता है?",
        "mechanism_hi": "टाइम-लैग रिवॉर्ड: दिमाग़ बाद में सही रास्ता चुनता है",
        "hook_angle": "direct-question",
        "structure": "problem-mechanism",
    },
    {
        "topic_hi": "ज़्यादा सोचना बंद कैसे करें",
        "question_hi": "बहुत ज़्यादा सोचते रहते हैं, कैसे रुकें?",
        "search_phrase_hi": "ज़्यादा सोचना बंद",
        "title_hi": "ज़्यादा सोचना बंद करने का असली तरीका क्या है?",
        "mechanism_hi": "रुमिनेशन लूप: दिमाग़ को एक टास्क पर बोदलो",
        "hook_angle": "direct-question",
        "structure": "problem-mechanism",
    },
    {
        "topic_hi": "अकेलापन क्यों लगता है",
        "question_hi": "भीड़ में भी अकेलापन क्यों लगता है?",
        "search_phrase_hi": "अकेलापन क्यों लगता है",
        "title_hi": "भीड़ में अकेलापन क्यों लगता है, वजह क्या है?",
        "mechanism_hi": "इमोशनल क्रेविंग: करीबी रिश्ते की कमी",
        "hook_angle": "direct-question",
        "structure": "problem-mechanism",
    },
    {
        "topic_hi": "ग़ुस्सा जल्दी आता है क्यों",
        "question_hi": "बहुत जल्दी ग़ुस्सा आ जाता है, कारण क्या है?",
        "search_phrase_hi": "ग़ुस्सा जल्दी आता है",
        "title_hi": "ग़ुस्सा जल्दी आता है तो इसका असली कारण क्या है?",
        "mechanism_hi": "अमिग्डाला हाइजैक: लिंबिक सिस्टम रिएक्ट करता है",
        "hook_angle": "direct-question",
        "structure": "problem-mechanism",
    },
    {
        "topic_hi": "किसी को भूल कैसे पाएं",
        "question_hi": "पुरानी यादें बार-बार आती हैं, कैसे भूलें?",
        "search_phrase_hi": "किसी को भूल कैसे",
        "title_hi": "किसी को भूलने का असली तरीका क्या होता है?",
        "mechanism_hi": "मेमोरी रिकंसॉलिडेशन: दिमाग़ को नया लूप दो",
        "hook_angle": "direct-question",
        "structure": "problem-mechanism",
    },
    {
        "topic_hi": "कम बात करने वालों की ताकत",
        "question_hi": "कम बोलने वाले लोग ज़्यादा क्यों जानते हैं?",
        "search_phrase_hi": "कम बात करने वाले",
        "title_hi": "कम बोलने वालों की असली ताकत क्या है?",
        "mechanism_hi": "ऑब्ज़र्वर इफ़ेक्ट: सुनने वाला ज़्यादा सीखता है",
        "hook_angle": "reversal",
        "structure": "problem-mechanism",
    },
    {
        "topic_hi": "असफलता से डर लगता है",
        "question_hi": "किसी काम में असफल होने का डर कैसे दूर करें?",
        "search_phrase_hi": "असफलता का डर",
        "title_hi": "असफलता का डर हमेशा के लिए कैसे ख़त्म करें?",
        "mechanism_hi": "फ़ेल्योर सेंसिटाइज़ेशन: छोटे स्टेप्स से टूटता है",
        "hook_angle": "direct-question",
        "structure": "problem-mechanism",
    },
    {
        "topic_hi": "किसी को इम्प्रेस कैसे करें",
        "question_hi": "किसी को अपनी तरफ़ आकर्षित कैसे करें?",
        "search_phrase_hi": "किसी को इम्प्रेस कैसे",
        "title_hi": "किसी को इम्प्रेस करने का सही तरीका क्या है?",
        "mechanism_hi": "मिरर इफ़ेक्ट: दूसरे जैसा बनो, फ़र्क घटाओ",
        "hook_angle": "direct-question",
        "structure": "problem-mechanism",
    },
]


def as_topics() -> list[Topic]:
    """Return the offline pool as Topic dataclass instances."""
    out: list[Topic] = []
    for raw in OFFLINE_TOPICS:
        topic = Topic(
            topic_hi=raw["topic_hi"],
            question_hi=raw["question_hi"],
            search_phrase_hi=raw["search_phrase_hi"],
            title_hi=raw["title_hi"],
            mechanism_hi=raw["mechanism_hi"],
            hook_angle=raw.get("hook_angle", "direct-question"),
            structure=raw.get("structure", "problem-mechanism"),
            search_phrases_hi=[raw["search_phrase_hi"]],
        )
        out.append(topic)
    return out