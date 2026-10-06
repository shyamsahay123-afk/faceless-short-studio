"""
ANTAR - Phase 2 test suite.

Proves the words half of the engine:

  - the audit catches every failure the lane cares about, with numbers
  - a broken script is refused, and a merely imperfect one still ships
  - the object resolver finds the thing a camera can point at
  - model ranking puts the strongest writer first and never picks a
    non-writing model
  - the writer climbs the model ladder, repairs short drafts, and returns the
    best draft of the run instead of nothing
  - the search box test parses the real reply format
  - the Hindi word band is derived from the measured voice, not guessed
  - JSON comes out of a messy reply
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from antar import config                                   # noqa: E402
from antar.brain import audit, models, objects, searchbox, topics as topic_engine  # noqa: E402
from antar.brain.providers import extract_json             # noqa: E402
from antar.brain.writer import write                       # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str):
    def wrap(fn):
        def run(verbose: bool = True):
            try:
                detail = fn() or ""
                RESULTS.append((name, True, str(detail)))
                if verbose:
                    print(f"  [PASS] {name}" + (f"   {detail}" if detail else ""))
                return True
            except AssertionError as exc:
                RESULTS.append((name, False, str(exc)))
                if verbose:
                    print(f"  [FAIL] {name}   {exc}")
                return False
            except Exception as exc:
                RESULTS.append((name, False, f"{type(exc).__name__}: {exc}"))
                if verbose:
                    print(f"  [FAIL] {name}   {type(exc).__name__}: {exc}")
                return False
        run.__name__ = fn.__name__
        return run
    return wrap


# ---------------------------------------------------------------- fixtures

GOOD_SCRIPT = {
    "title_hi": "लोग आपको इग्नोर क्यों करते हैं",
    "closing_echo": "जब वो जवाब नहीं देता, तुम्हारा फ़ोन मेज़ पर पड़ा रहता है।",
    "peak_line": 9,
    "beats": [
        {"line_hi": "जब वो जवाब नहीं देता, तुम्हारा फ़ोन मेज़ पर पड़ा रहता है।", "object_hi": "फ़ोन", "role": "hook"},
        {"line_hi": "तुम उसी मग को देखते रहते हो, जो कल से रखा है।", "object_hi": "मग", "role": "build"},
        {"line_hi": "हर बार वही दीवार, वही रोशनी, वही चुप्पी।", "object_hi": "दीवार", "role": "build"},
        {"line_hi": "तुम्हारा दिमाग़ इस खाली कुर्सी पर एक पूरी कहानी बना देता है।", "object_hi": "कुर्सी", "role": "turn"},
        {"line_hi": "वो कहानी घड़ी की सुई के साथ बढ़ती जाती है।", "object_hi": "घड़ी", "role": "build"},
        {"line_hi": "सच यह है कि बंद दरवाज़ा तुम्हारे बारे में कुछ नहीं कहता।", "object_hi": "दरवाज़ा", "role": "turn"},
        {"line_hi": "वो अपनी खिड़की बंद कर रहा है, तुम्हारी नहीं।", "object_hi": "खिड़की", "role": "build"},
        {"line_hi": "तुम्हारी चुप्पी धीरे-धीरे उसी कमरे में जमा जाती है।", "object_hi": "कमरा", "role": "build"},
        {"line_hi": "वो फ़ोन जो मेज़ पर पड़ा है, तुम्हारी कीमत नहीं तय करता।", "object_hi": "फ़ोन", "role": "payoff"},
    ],
}


def clone(script: dict) -> dict:
    import copy
    return copy.deepcopy(script)


# ---------------------------------------------------------------- the audit

@check("a good script passes the audit")
def t_audit_good():
    cfg = config.load()
    band = tuple(cfg["pacing"]["band_words"])
    report = audit.audit(GOOD_SCRIPT, cfg["pacing"]["render_floor_words"],
                         cfg["pacing"]["render_ceiling_words"], band)
    assert not report.blocked, f"a good script was blocked: {[f.detail for f in report.of('BLOCK')]}"
    assert not report.of("WARN"), f"a good script raised warnings: {[f.detail for f in report.of('WARN')]}"
    assert report.score() == 100, f"a clean script scored {report.score()}, expected 100"
    assert report.objects_found == report.beats == 9, "not every beat resolved an object"
    return f"{report.words} words, {report.beats} beats, all objects found, score 100/100"


@check("a too-short script is blocked, with the count in the message")
def t_audit_short():
    script = clone(GOOD_SCRIPT)
    script["beats"] = script["beats"][:3]
    report = audit.audit(script, 70, 110, (78, 102))
    assert report.blocked, "a 3-beat script was accepted"
    length = [f for f in report.of("BLOCK") if f.check == "length"]
    assert length, "it was blocked for the wrong reason"
    assert str(report.words) in length[0].detail, "the word count is not in the message"
    return f"{report.words} words blocked: {length[0].detail[:52]}"


@check("a too-long script is blocked")
def t_audit_long():
    script = clone(GOOD_SCRIPT)
    script["beats"] = script["beats"] * 2
    report = audit.audit(script, 70, 110, (78, 102))
    assert report.blocked, "an over-long script was accepted"
    assert any(f.check == "length" for f in report.of("BLOCK")), "wrong reason"
    return f"{report.words} words blocked"


@check("a name anywhere blocks the script")
def t_audit_names():
    script = clone(GOOD_SCRIPT)
    script["beats"][2]["line_hi"] = "हर बार वही दीवार, जैसे कार्लोस ने कहा था।"
    report = audit.audit(script, 70, 110, (78, 102))
    assert report.blocked, "a script naming a person was accepted"
    assert any(f.check == "names" for f in report.of("BLOCK")), "wrong reason"
    return "कार्लोस was caught and blocked"


@check("आप warns, तुम scores clean, and NOTEs cost nothing")
def t_audit_address():
    polite = clone(GOOD_SCRIPT)
    polite["beats"][1]["line_hi"] = "आप उसी मग को देखते रहते हैं, जो कल से वैसे ही रखा है।"
    report = audit.audit(polite, 70, 110, (78, 102))
    assert any(f.check == "address" and f.level == "WARN" for f in report.findings), "आप was not flagged"

    report2 = audit.audit(GOOD_SCRIPT, 70, 110, (78, 102))
    notes = len(report2.of("NOTE"))
    assert report2.score() == 100 and notes > 0, (
        f"{notes} notes should not reduce a perfect score, got {report2.score()}")
    return f"आप warns, and {notes} NOTES still score 100/100"


@check("the peak is checked against its position, not its wording")
def t_audit_peak():
    script = clone(GOOD_SCRIPT)
    script["peak_line"] = 2               # the strongest line buried near the top
    report = audit.audit(script, 70, 110, (78, 102))
    assert any(f.check == "peak" and f.level == "WARN" for f in report.findings), \
        "a buried peak was not flagged"
    return "peak at beat 2 of 9 flagged as WARN"


@check("a missing loop is caught by counting shared words")
def t_audit_loop():
    script = clone(GOOD_SCRIPT)
    script["closing_echo"] = "यह सब बहुत पुरानी बात है।"
    report = audit.audit(script, 70, 110, (78, 102))
    assert any(f.check == "loop" and f.level == "WARN" for f in report.findings), \
        "a closing line that echoes nothing was accepted"
    return "unrelated closing line flagged"


@check("a beat with nothing filmable is flagged, not ignored")
def t_audit_object_missing():
    script = clone(GOOD_SCRIPT)
    script["beats"][4]["line_hi"] = "तुम्हारा आत्मविश्वास धीरे-धीरे कम होता जाता है।"
    script["beats"][4]["object_hi"] = ""
    report = audit.audit(script, 70, 110, (78, 102))
    misses = [f for f in report.of("WARN") if f.check == "object"]
    assert misses, "a line with no object passed unnoticed"
    assert report.objects_found == 8, f"expected 8 resolved objects, got {report.objects_found}"
    return "beat 5 flagged: nothing a camera can point at"


# ---------------------------------------------------------------- objects

@check("the object resolver finds the filmable word")
def t_objects():
    query, word = objects.resolve("तुम उसी मग को देखते रहते हो।")
    assert query == "coffee mug on table", f"wrong query: {query}"
    assert word == "मग", f"wrong word: {word}"

    query2, word2 = objects.resolve("कुछ भी नहीं", hint="खिड़की")
    assert query2 == "window at night", f"the writer's own hint was ignored: {query2}"

    assert objects.resolve("आत्मविश्वास कम होता जाता है") is None, \
        "a feeling was mistaken for an object"
    finding = objects.resolve("तुम्हारा दिमाग़ इस खाली कुर्सी पर कहानी बनाता है।")
    assert finding and finding[1] == "कुर्सी", f"wrong pick: {finding}"
    return "मग, कुर्सी found; a feeling correctly returns nothing"


@check("no object query sends a human to the stock library")
def t_objects_no_faces():
    import re
    people = ("man", "woman", "person", "people", "hand", "hands", "face",
              "couple", "crowd", "guy", "girl", "boy", "worker", "portrait",
              "smiling", "laughing", "walking", "talking")
    offenders = []
    for key, query in objects.OBJECTS.items():
        for word in people:
            # word boundaries, so 'surface' does not look like 'face'
            if re.search(rf"\b{word}\b", query.lower()):
                offenders.append(f"{key}->{query}")
                break
    assert not offenders, f"face-hunting queries in the dictionary: {offenders[:4]}"
    return f"{len(objects.OBJECTS)} objects, none asking for a person"


# ---------------------------------------------------------------- models

@check("model ranking puts the stronger writing model first")
def t_model_rank():
    ids = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "whisper-large-v3",
           "llama-3.1-8b-instant", "groq/compound-mini"]
    ranked = models.rank("groq", ids)
    names = [c.model for c in ranked]
    assert "whisper-large-v3" not in names, "a transcription model was offered as a writer"
    assert names[0] == "openai/gpt-oss-120b", f"wrong winner: {names[0]}"
    assert names.index("openai/gpt-oss-120b") < names.index("openai/gpt-oss-20b"), \
        "120b did not beat 20b"
    assert names.index("openai/gpt-oss-20b") < names.index("groq/compound-mini"), \
        "20b did not beat a mini model"
    return " > ".join(names)


@check("a newer generation beats an older one of the same size")
def t_model_generation():
    ranked = models.rank("gemini", ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.1-flash-lite"])
    names = [c.model for c in ranked]
    assert names[0] == "gemini-3.8-flash", f"wrong winner: {names}"
    assert names[-1] == "gemini-3.1-flash-lite", f"lite model not last: {names}"
    return " > ".join(names)


@check("no writing model is excluded by accident")
def t_model_writer_filter():
    assert models.is_writer("openai/gpt-oss-120b")
    assert models.is_writer("gemini-3.8-flash")
    assert not models.is_writer("whisper-large-v3")
    assert not models.is_writer("text-embedding-3-small")
    return "writers kept, transcriber and embedder excluded"


# ---------------------------------------------------------------- writer

class FakeBrain:
    """A brain with no network. Records every model it is asked for."""

    def __init__(self, catalogue: dict, replies: dict):
        self.catalogue = catalogue
        self.replies = replies          # model name -> list of replies
        self.asked: list[str] = []
        self.spent: dict[str, int] = {}

    def list_models(self, service: str) -> list[str]:
        return self.catalogue.get(service, [])

    def call(self, prompt, model, service="groq", system="", temperature=0.85, max_tokens=4000):
        self.asked.append(model)
        self.spent[model] = self.spent.get(model, 0) + 1
        queue = self.replies.get(model, [])
        index = self.spent[model] - 1
        if index >= len(queue):
            return False, "", "no more replies queued"
        reply = queue[index]
        if isinstance(reply, tuple):
            return reply
        import json
        return True, json.dumps(reply, ensure_ascii=False), ""


def _cfg():
    return config.load()


TOPIC = topic_engine.Topic(
    topic_hi="लोग तुम्हें क्यों नज़रअंदाज़ करते हैं",
    question_hi="मुझे इग्नोर क्यों किया जाता है",
    search_phrase_hi="लोग इग्नोर क्यों करते हैं",
    title_hi="लोग तुम्हें क्यों नज़रअंदाज़ करते हैं",
    mechanism_hi="दिमाग़ एक बार में एक ही बात पकड़ता है",
    hook_angle="direct-question", structure="problem-mechanism")


@check("the writer takes the answer from the strongest model")
def t_writer_strongest():
    brain = FakeBrain(
        {"groq": ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]},
        {"openai/gpt-oss-120b": [GOOD_SCRIPT]})
    result = write(brain, TOPIC, _cfg())
    assert result.ok, f"no script: {result.note}"
    assert result.model == "openai/gpt-oss-120b", f"wrong model wrote it: {result.model}"
    assert brain.asked == ["openai/gpt-oss-120b"], f"it asked more than it needed to: {brain.asked}"
    return f"written by {result.model}, {result.report.words} words, score {result.report.score()}"


@check("a weak answer does not stop the engine reaching a strong one")
def t_writer_climbs():
    short = {"beats": [{"line_hi": "तुम अकेले हो।", "object_hi": "", "role": "hook"}],
             "title_hi": "कुछ", "peak_line": 1}
    brain = FakeBrain(
        {"groq": ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]},
        {"openai/gpt-oss-120b": [(False, "", "400 bad request")],
         "openai/gpt-oss-20b": [short, GOOD_SCRIPT]})
    result = write(brain, TOPIC, _cfg())
    assert result.ok, f"no script: {result.note}"
    assert "openai/gpt-oss-120b" in brain.asked, "the strong model was never tried"
    assert "openai/gpt-oss-20b" in brain.asked, "the engine did not climb to the next model"
    assert result.model == "openai/gpt-oss-20b", f"wrong author: {result.model}"
    assert len(result.attempts) >= 2, f"the ladder is not recorded: {result.attempts}"
    return f"tried {brain.asked}, answer from {result.model}"


@check("an unparseable reply is skipped, not fatal")
def t_writer_bad_json():
    brain = FakeBrain(
        {"groq": ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]},
        {"openai/gpt-oss-120b": ["I cannot help with that."],
         "openai/gpt-oss-20b": [GOOD_SCRIPT]})
    result = write(brain, TOPIC, _cfg())
    assert result.ok, f"no script: {result.note}"
    assert result.model == "openai/gpt-oss-20b", f"wrong author: {result.model}"
    return "prose reply skipped, next model answered"


@check("a too-short draft is sent back once to grow")
def t_writer_repair():
    short = {"title_hi": "कुछ", "peak_line": 1, "beats": [
        {"line_hi": "जब वो जवाब नहीं देता, तुम्हारा फ़ोन मेज़ पर रहता है।", "object_hi": "फ़ोन", "role": "hook"},
        {"line_hi": "सच यह है कि वो फ़ोन तुम्हारी कीमत नहीं तय करता।", "object_hi": "फ़ोन", "role": "payoff"}]}
    brain = FakeBrain(
        {"groq": ["openai/gpt-oss-120b"]},
        {"openai/gpt-oss-120b": [short, GOOD_SCRIPT]})
    result = write(brain, TOPIC, _cfg())
    assert result.ok, f"no script: {result.note}"
    assert brain.spent["openai/gpt-oss-120b"] == 2, \
        f"the short draft was not sent back (calls: {brain.spent})"
    assert result.report.words > 70, f"the repair did not lengthen it: {result.report.words}"
    return f"asked to extend, grew to {result.report.words} words"


@check("a blocked draft is still returned, with its complaints attached")
def t_writer_never_ends_empty():
    brain = FakeBrain(
        {"groq": ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]},
        {"openai/gpt-oss-120b": [(False, "", "429 rate limited")],
         "openai/gpt-oss-20b": [(False, "", "network failure")]})
    result = write(brain, TOPIC, _cfg())
    assert not result.ok, "it claimed to have a script when every call failed"
    assert "every model failed" in result.note or "network" in result.note, f"unhelpful note: {result.note}"
    assert len(result.attempts) == 2, f"attempts not recorded: {result.attempts}"
    return "every model failed and it said so plainly, rather than inventing a script"


# ---------------------------------------------------------------- search box

@check("the search box test parses the real reply format")
def t_searchbox_parse():
    wrapped = 'window.google.ac.h(["शर्मीले लोग",[["शर्मीले लोगो",0],["शर्मीले लोग क्यों",0]],{}])'
    parsed = searchbox._parse(wrapped)
    assert parsed == ["शर्मीले लोगो", "शर्मीले लोग क्यों"], f"wrong parse: {parsed}"

    plain = '["q",["one","two"]]'
    assert searchbox._parse(plain) == ["one", "two"], "plain JSON was not handled"
    assert searchbox._parse("not json at all") == [], "garbage did not return empty"
    assert searchbox._parse("") == [], "empty input did not return empty"
    return "JS-wrapped, plain, garbage and empty all handled"


@check("the signal is a count, not an opinion")
def t_searchbox_signal(monkeypatch=None):
    original = searchbox.suggest

    searchbox.suggest = lambda phrase, timeout=10: ["लोग इग्नोर क्यों करते हैं",
                                                    "लोग इग्नोर क्यों", "लोग इग्नोर होने पर"]
    try:
        result = searchbox.test("लोग इग्नोर क्यों करते हैं")
        assert result["signal"] == "strong", f"expected strong, got {result['signal']}"
        assert result["hits"] >= 3, f"wrong hit count: {result['hits']}"

        searchbox.suggest = lambda phrase, timeout=10: ["बिल्कुल अलग बात"]
        thin = searchbox.test("लोग इग्नोर क्यों करते हैं")
        assert thin["signal"] == "thin", f"expected thin, got {thin['signal']}"

        searchbox.suggest = lambda phrase, timeout=10: []
        none = searchbox.test("लोग इग्नोर क्यों करते हैं")
        assert none["signal"] == "none", f"expected none, got {none['signal']}"
    finally:
        searchbox.suggest = original
    return "strong / thin / none all classified by count"


# ---------------------------------------------------------------- lane test

@check("the lane test refuses a title made of pictures")
def t_lane_footage():
    bad = topic_engine.Topic("बर्फ़", "q", "बर्फ़ और धुआँ", "बर्फ़ पर पड़ी धुआँ की छाया क्यों दिखती है",
                             "m", "direct-question", "loop-question")
    failures = topic_engine.lane_test(bad, 40, 60)
    assert any("footage" in f for f in failures), f"a picture-title passed: {failures}"
    return f"refused: {[f[:44] for f in failures][0]}"


@check("the lane test refuses banned framing and names")
def t_lane_banned():
    bad = topic_engine.Topic("स्टोइक तरीका", "q", "p", "स्टोइक तरीका कैसे काम करता है और क्यों",
                             "m", "contrarian", "micro-story")
    failures = topic_engine.lane_test(bad, 20, 80)
    assert any("banned" in f for f in failures), f"stoic framing passed: {failures}"

    named = topic_engine.Topic("राहुल की कहानी", "q", "p", "राहुल को क्यों इग्नोर किया जाता है",
                               "m", "recognition", "micro-story")
    failures2 = topic_engine.lane_test(named, 20, 80)
    assert any("name" in f for f in failures2), f"a name passed: {failures2}"
    return "stoic framing and an invented name both refused"


@check("the lane test refuses a topic with no answer")
def t_lane_mechanism():
    bad = topic_engine.Topic("चुप्पी", "q", "p", "लोग चुप क्यों हो जाते हैं और बात क्यों नहीं करते",
                             "", "direct-question", "problem-mechanism")
    failures = topic_engine.lane_test(bad, 20, 80)
    assert any("mechanism" in f for f in failures), f"an answerless topic passed: {failures}"
    return "no mechanism = refused"


@check("a proper Lane B topic passes")
def t_lane_pass():
    cfg = config.load()
    good = topic_engine.Topic(
        "लोग तुम्हें क्यों नज़रअंदाज़ करते हैं",
        "मुझे इग्नोर क्यों किया जाता है",
        "लोग इग्नोर क्यों करते हैं",
        "लोग तुम्हें क्यों नज़रअंदाज़ करते हैं",
        "दिमाग़ एक बार में एक ही बात पकड़ता है",
        "direct-question", "problem-mechanism")
    failures = topic_engine.lane_test(good, cfg["topics"]["title_min_chars"],
                                      cfg["topics"]["title_max_chars"])
    assert not failures, f"a good topic was refused: {failures}"
    return "passed every lane check"


# ---------------------------------------------------------------- parsing

@check("JSON comes out of a messy reply")
def t_extract_json():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('Sure!\n```json\n{"a": 1}\n```\nHope that helps.') == {"a": 1}
    assert extract_json('{"a": 1,}') == {"a": 1}, "a trailing comma was fatal"
    assert extract_json('text {"a": {"b": 2}} more') == {"a": {"b": 2}}, "nested object lost"
    assert extract_json("no json here") is None
    assert extract_json("") is None
    return "fences, prose, trailing commas and nesting all handled"


# ---------------------------------------------------------------- pacing

@check("the Hindi word band comes from the measured voice")
def t_pacing_derivation():
    cfg = config.load()
    wps = cfg["pacing"]["words_per_second"]
    band = cfg["pacing"]["band_words"]
    overhead = cfg["pacing"]["silence_before_payoff"] + cfg["pacing"]["loop_gap"]
    low, high = cfg["pacing"]["target_band_seconds"]

    expected_low = wps * (low - overhead)
    expected_high = wps * (high - overhead)
    assert abs(expected_low - band[0]) <= 2, \
        f"band floor {band[0]} does not follow from {wps} x {low - overhead:.2f} = {expected_low:.1f}"
    assert abs(expected_high - band[1]) <= 2, \
        f"band ceiling {band[1]} does not follow from {wps} x {high - overhead:.2f} = {expected_high:.1f}"
    assert cfg["pacing"]["render_floor_words"] < band[0] < band[1] < cfg["pacing"]["render_ceiling_words"], \
        "floor and ceiling do not straddle the band"
    return (f"{wps} w/s x ({low}-{overhead:.2f})s = {expected_low:.0f}, "
            f"x ({high}-{overhead:.2f})s = {expected_high:.0f} -> band {band}")


@check("the config still refuses a build that breaks a locked rule")
def t_config_guard():
    import json as _json
    from antar.config import Config, ConfigError
    good = _json.loads(config.config_path().read_text(encoding="utf-8"))
    broken = _json.loads(_json.dumps(good))
    broken["script"]["address"] = "आप"
    try:
        Config(broken, config.config_path()).validate()
    except ConfigError as exc:
        assert "address" in str(exc), "wrong guard fired"
        return "address=आप was refused"
    raise AssertionError("a build addressing the viewer as आप was allowed")


ALL = [
    t_audit_good, t_audit_short, t_audit_long, t_audit_names, t_audit_address,
    t_audit_peak, t_audit_loop, t_audit_object_missing,
    t_objects, t_objects_no_faces,
    t_model_rank, t_model_generation, t_model_writer_filter,
    t_writer_strongest, t_writer_climbs, t_writer_bad_json, t_writer_repair,
    t_writer_never_ends_empty,
    t_searchbox_parse, t_searchbox_signal,
    t_lane_footage, t_lane_banned, t_lane_mechanism, t_lane_pass,
    t_extract_json, t_pacing_derivation, t_config_guard,
]


def run_all(verbose: bool = True) -> bool:
    RESULTS.clear()
    if verbose:
        print()
        print("  ANTAR - PHASE 2 SELF TEST")
        print("  " + "-" * 62)
    import time
    started = time.time()
    for test in ALL:
        test(verbose=verbose)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    if verbose:
        print("  " + "-" * 62)
        print(f"  {passed}/{total} passed in {time.time()-started:.2f}s")
        if passed != total:
            print("  failing:")
            for name, ok, detail in RESULTS:
                if not ok:
                    print(f"    - {name}: {detail}")
        print()
    return passed == total


if __name__ == "__main__":
    raise SystemExit(0 if run_all(verbose=True) else 1)
