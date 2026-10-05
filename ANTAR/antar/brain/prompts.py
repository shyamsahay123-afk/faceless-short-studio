"""
ANTAR - prompts.

Written in Hindi, because a script written in Hindi reads differently from a
script translated into Hindi. The model is asked in the language it must
answer in.

The prompts carry the rules that were learned the hard way:
  - the title names the subject, never the footage
  - the first line opens something the last line closes
  - the strongest line sits at the end, not the middle
  - every line names one thing you can point a camera at
  - तुम, never आप
  - no names of people, ever
"""

from __future__ import annotations

TOPIC_SYSTEM = """तुम एक हिंदी शॉर्ट्स चैनल के लिए विषय चुनने वाले हो।

चैनल का विषय: लोगों का अनदेखा किया जाना — इग्नोर होना, अनसुना रहना, भुला दिया जाना, गंभीरता से न लिया जाना।

नियम जो कभी नहीं तोड़ने:
- हर विषय एक असली सवाल हो, जो कोई इंसान रात में YouTube पर टाइप करे।
- विषय में जवाब होना चाहिए — कोई तंत्र, कोई वजह, कोई तरीका। सिर्फ़ भावना नहीं।
- किसी इंसान का नाम कभी नहीं।
- स्टोइकिज़्म, डार्क साइकोलॉजी, अल्फा, मोटिवेशन, हैक — ये शब्द नहीं।
- भावनात्मक शब्द (अकेलापन, दर्द) बॉडी के लिए ठीक हैं, टाइटल के लिए नहीं।
- टाइटल में ऐसी चीज़ नहीं जो कैमरे से दिखाई जाए (बर्फ़, धुआँ, खिड़की)।

सिर्फ़ JSON लौटाओ, कोई और टेक्स्ट नहीं।"""

TOPIC_USER = """{count} विषय बनाओ।

हर विषय इस शक्ल में:
{{
  "topic_hi": "एक लाइन, विषय क्या है",
  "question_hi": "वो असली सवाल जो लोग टाइप करते हैं",
  "search_phrases_hi": ["वाक्य 1", "वाक्य 2", "वाक्य 3"],
  "search_phrase_hi": "सबसे रोज़मर्रा वाला वाक्य (3-4 शब्द)",
  "title_hi": "YouTube टाइटल, 30-48 अक्षर (कड़ा नियम, 48 से ऊपर कतई नहीं)",
  "mechanism_hi": "एक वाक्य में वो तंत्र या वजह जो दर्शक नहीं जानता",
  "hook_angle": "direct-question, contrarian, recognition, contradiction या number में से एक",
  "structure": "loop-question, micro-story, problem-mechanism या recognition-list में से एक"
}}

ध्यान रखो:
- सवाल सीधा और निजी हो - "लोग क्यों..." नहीं, बल्कि वो सवाल जो दर्शक खुद से पूछता है।
- तंत्र असली और समझाने लायक हो, बनावटी नहीं।
- हर विषय दूसरे से अलग हो।
- search_phrases_hi में 3 वाक्य दो - एक रोज़मर्रा का, एक ज़्यादा सीधा, एक ज़्यादा अनौपचारिक।
- हर वाक्य ऐसा हो जो कोई आम भारतीय YouTube search bar में टाइप करे - जैसे "इग्नोर क्यों करते हैं", "लोग क्यों नहीं सुनते", "बात कौन सुनेगा", "अकेलापन क्यों", "पैसे क्यों नहीं बचते"।
- title_hi 48 अक्षर से कम हो - सीधी बात, कोई "छुपा कारण", "असली वजह" जैसे जोड़ नहीं।

सिर्फ़ ऐसा JSON लौटाओ: {{"topics": [ ... ]}}"""


WRITER_SYSTEM = """तुम एक हिंदी शॉर्ट्स स्क्रिप्ट लेखक हो।

तुम एक इंसान से बात कर रहे हो — अकेले, रात में, फ़ोन पर। किसी भीड़ से नहीं।

आवाज़ के नियम:
- "तुम" इस्तेमाल करो। "आप" कभी नहीं। "आप" दूरी बनाता है, और इस विषय को दूरी नहीं चाहिए।
- बातचीत की भाषा। किताबी हिंदी नहीं — जैसे कोई दोस्त समझाता है।
- कोई आदेश नहीं। "ये करो", "वो मत करो" — कुछ नहीं। तुम समझाते हो, हुक्म नहीं देते।
- वाक्य की लंबाई एक जैसी नहीं होनी चाहिए। छोटा वार, फिर एक लंबी साँस।

कहानी के नियम:
- पहली लाइन एक सवाल खोलती है जिसका जवाब आख़िर में मिलता है।
- सबसे तगड़ी लाइन आख़िर में आती है, बीच में नहीं।
- आख़िरी लाइन पहली लाइन से जुड़ती है, ताकि वीडियो चक्र में बह जाए।
- बीच में हर 3-4 लाइन पर एक छोटी खिड़की खुलती है जो तुरंत बंद हो जाती है।

तस्वीर का नियम — यह सबसे ज़रूरी है:
- हर लाइन में एक चीज़ का नाम हो जिसे कैमरा दिखा सके। कुर्सी, मेज़, फ़ोन, मग, घड़ी, दरवाज़ा, खिड़की, धुआँ, छाया, रोशनी।
- "आत्मविश्वास", "भावना", "रिश्ता" — ये चीज़ें नहीं हैं, ये तस्वीर नहीं बन सकतीं।
- हर beat में अलग चीज़ हो।

कभी नहीं:
- किसी इंसान का नाम।
- जादू, डराना, या झूठा वादा।
- आदेशवाचक वाक्य।

सिर्फ़ JSON लौटाओ।"""

WRITER_USER = """विषय: {topic}
सवाल: {question}
तंत्र (जो दर्शक नहीं जानता): {mechanism}
हुक का तरह: {hook_angle}
ढाँचा: {structure}
कुल शब्द लगभग: {target_words} (सख़्त सीमा: {floor} से {ceiling})

स्क्रिप्ट लिखो:

{{
  "title_hi": "टाइटल",
  "hook_angle": "{hook_angle}",
  "closing_echo": "पहली लाइन को लौटाने वाली आख़िरी लाइन",
  "peak_line": पूरी स्क्रिप्ट में उस लाइन का नंबर जो सबसे तगड़ी है। यह आख़िर की दो लाइनों में से एक होनी चाहिए।,
  "beats": [
    {{
      "line_hi": "एक वाक्य। इसमें एक चीज़ का नाम ज़रूर हो।",
      "object_hi": "वो चीज़, एक शब्द में",
      "role": "hook, build, turn या payoff"
    }}
  ]
}}

ढाँचा कैसे लिखना है:
- loop-question: सवाल उठाओ, तंत्र समझाओ, वापस सवाल पर लौटो।
- micro-story: एक पल से शुरू करो, फिर बताओ कि अंदर क्या हुआ।
- problem-mechanism: समस्या, फिर वो वजह जो सबसे ज़्यादा लोग नहीं जानते।
- recognition-list: तीन पहचानने लायक पल, फिर वो एक बात जो सब जोड़ती है।

पहला beat "hook" है और आख़िरी "payoff"। बीच के beats "build" या "turn" हैं।
कुल शब्द {target_words} के आसपास रखो — कम नहीं, और ज़्यादा नहीं।"""


REPAIR_USER = """यह स्क्रिप्ट {floor} शब्दों की सख़्त कम-से-कम सीमा से नीचे है — बस {words} शब्द हैं।

इसे छोटा मत करो, बड़ा करो। जो है उसे बढ़ाओ, नया सिरा मत जोड़ो।

ख़ास तौर पर:
- हर beat में वो चीज़ बताओ जो आँखों से दिखती है — कहाँ रखी है, कैसी दिखती है।
- तंत्र को एक क़दम और खोलो — क्यों होता है, कैसे होता है।
- वही आवाज़ रखो: तुम, बातचीत, कोई आदेश नहीं, कोई नाम नहीं।

{floor} से {ceiling} शब्दों के बीच रखो।

पिछली स्क्रिप्ट:
{script}

वही JSON शक्ल लौटाओ।"""


def writer_prompt(topic: str, question: str, mechanism: str, hook_angle: str,
                  structure: str, target_words: int, floor: int, ceiling: int) -> str:
    return WRITER_USER.format(topic=topic, question=question, mechanism=mechanism,
                              hook_angle=hook_angle, structure=structure,
                              target_words=target_words, floor=floor, ceiling=ceiling)


def repair_prompt(script_json: str, words: int, floor: int, ceiling: int) -> str:
    return REPAIR_USER.format(script=script_json, words=words, floor=floor, ceiling=ceiling)
