"""
Phase 7 self tests - the details stage.

What is being tested, and why each of these exists:

  - the harvest only keeps suggestions whose every word belongs to this video.
    A live run collected "लोग इग्नोर क्यों करते हैं कबूतर" (a real suggestion
    about pigeons) and the generator would have made it the title.
  - a title is built on a WHOLE search phrase, never a fragment. An earlier
    version earned the full 35 search points for the single word "इग्नोर" and
    built titles around it.
  - the generator and the check suite score against the same phrase list. The
    generator wrote its list into the details file; if the suite scores against
    a different list, a good title reads as a failure.
  - the description carries the search phrase inside the first 100 characters,
    3-5 hashtags that are subject words, 10-15 plain keywords with no hashtags,
    and a pinned comment that asks for a sentence.
  - audit() fails a payload that breaks any of those rules, so the stage cannot
    pass itself by accident.

No network is required: the harvest filter, the writer, the scorer and the
assembler are all exercised on recorded, real data. The one live call is made
against a nonsense topic, where both "nothing came back" and "the connection is
down" are acceptable outcomes and the stage must still say why.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from antar import config                                        # noqa: E402
from antar.checks import suite, titlescore                      # noqa: E402
from antar.checks.report import PASS, FAIL                      # noqa: E402
from antar.details import DetailsError, assemble, harvest, run   # noqa: E402
from antar.details import writer                                 # noqa: E402

from tests.test_phase6 import (base_bundle, base_script, find,  # noqa: E402
                              run_bundle)

RESULTS: list[tuple[str, bool, str]] = []
WRITTEN: list[Path] = []
TEST_ID = "TEST7_DETAILS"

# The real topic this render was written for, and a real phrase list, recorded
# from the live autocomplete endpoint on the day this phase was built.
TOPIC_PHRASE = "लोग इग्नोर क्यों करते हैं"
PHRASES = [
    TOPIC_PHRASE,
    "लोग इग्नोर क्यों करते हैं कहां है",
    "लोग तुम्हें क्यों नज़रअंदाज़ करते हैं कहां है",
]


def check(name: str):
    def wrap(fn):
        def run_it(verbose: bool = True):
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
        return run_it
    return wrap


def fixture_script(render_id: str = TEST_ID) -> dict:
    """A script shaped exactly like the real one, with the real topic."""
    script = base_script(render_id)
    script["topic"]["search_phrase_hi"] = TOPIC_PHRASE
    script["topic"]["mechanism_hi"] = "नज़रअंदाज़ करना एक चुप्पी से शुरू होता है"
    return script


def keep(path: Path) -> Path:
    WRITTEN.append(path)
    return path


# ------------------------------------------------------------------- harvest

@check("the harvest starts from the topic's own phrase, never a bare stem")
def t_roots():
    roots = harvest.root_phrases(fixture_script())
    assert roots and roots[0] == TOPIC_PHRASE, roots
    assert all(len(r.split()) >= 2 for r in roots), f"a one-word stem was used: {roots}"
    return f"roots: {' | '.join(roots)[:60]}"


@check("a suggestion may only use words this video is actually about")
def t_off_topic_is_rejected():
    script = fixture_script()
    beats = script["script"]["beats"]
    vocab = harvest._vocabulary(*(harvest.root_phrases(script)
                                  + [b["line_hi"] for b in beats]))
    assert harvest._allowed(TOPIC_PHRASE, vocab), "the topic's own phrase was rejected"
    assert harvest._allowed("लोग इग्नोर क्यों करते हैं कहां है", vocab), \
        "a real on-topic suggestion was rejected"
    # both of these came back from the live endpoint during the build
    assert not harvest._allowed("लोग इग्नोर क्यों करते हैं कबूतर", vocab), \
        "the pigeon suggestion passed the filter"
    assert not harvest._allowed("लोग क्यों मोहब्बत किया करते हैं", vocab), \
        "a suggestion about love passed the filter"
    return "pigeon and love rejected, the topic phrase kept"


@check("a topic nobody searches for returns an empty harvest with a reason")
def t_empty_harvest_is_honest():
    script = fixture_script()
    script["topic"]["search_phrase_hi"] = "ज़्क़्व प्लम्ब थ्रिक्स"
    script["topic"]["title_hi"] = "ज़्क़्व प्लम्ब थ्रिक्स"
    script["topic"]["mechanism_hi"] = "ज़्क़्व प्लम्ब थ्रिक्स"
    payload = harvest.harvest(script, extra_probes=[])
    assert "phrases" in payload and "note" in payload
    if payload["phrases"]:
        assert all("ज़्क़्व" in p for p in payload["phrases"]), \
            f"an off-topic phrase got through: {payload['phrases'][:3]}"
        return f"{len(payload['phrases'])} suggestion(s), all on topic"
    assert "search phrase" in payload["note"], payload["note"]
    return "empty, and the note says where the points come from instead"


@check("the harvest file round-trips through disk")
def t_harvest_round_trip():
    cfg = config.load()
    payload = {"phrases": PHRASES, "sources": [], "note": "test", "when": 0.0}
    path = keep(harvest.save(cfg, TEST_ID, payload))
    assert path.exists(), f"nothing written to {path}"
    back = harvest.load(cfg, TEST_ID)
    assert back and back["phrases"] == PHRASES, back
    return f"{path.name}: {len(PHRASES)} phrase(s) read back"


# -------------------------------------------------------------------- writer

@check("every candidate is built on a whole search phrase, inside the band")
def t_candidates_use_whole_phrases():
    script = fixture_script()
    scored, best, written = writer.candidates(None, PHRASES, script)
    assert len(scored) >= 3, f"only {len(scored)} candidate(s)"
    low, high = 30, 48
    for row in scored:
        assert low <= row["characters"] <= high, f"{row['title']} is {row['characters']} chars"
        hit, why, how_much = titlescore.phrase_hit(row["title"], PHRASES)
        assert how_much == 1.0, f"{row['title']} only reached {how_much} on the phrase: {why}"
        assert not any(ord(c) < 128 and c.isalpha() for c in row["title"]), \
            f"Latin script in the title: {row['title']}"
    assert best == scored[0]["title"], (best, scored[0]["title"])
    assert best in [row["title"] for row in scored]
    return f"{len(scored)} candidates, best {best!r} ({scored[0]['total']}/100)"


@check("an off-topic suggestion can never reach a title")
def t_off_topic_never_becomes_a_title():
    script = fixture_script()
    dirty = PHRASES + ["लोग इग्नोर क्यों करते हैं कबूतर", "लोग क्यों मोहब्बत किया करते हैं"]
    scored, best, _ = writer.candidates(None, dirty, script)
    for row in scored:
        for bad in ("कबूतर", "मोहब्बत", "दिमाग"):
            assert bad not in row["title"], f"{bad} reached a title: {row['title']}"
    return f"{len(scored)} candidates, none carry an off-topic word"


@check("a one-word fragment never earns the search points")
def t_fragment_never_earns_the_points():
    cfg = config.load()
    hit, why, how_much = titlescore.phrase_hit("लोग इग्नोर क्यों करते हैं और अकेलेपन का सच",
                                               ["इग्नोर"])
    assert hit == "" and how_much == 0.0, f"a fragment matched: {hit} {how_much}"
    scored = titlescore.score("इग्नोर का सच", cfg, phrases=["इग्नोर"])
    part = next(p for p in scored["parts"] if p["part"] == "search phrase")
    assert part["points"] == 0, f"a fragment scored {part['points']}/35"
    assert not scored["pass"], "a title with no real phrase passed the gate"
    return f"fragment -> {part['points']}/35, total {scored['total']}/100"


@check("part of a phrase earns part of the points, and the note says so")
def t_partial_phrase_earns_part():
    cfg = config.load()
    # every word of the phrase, in order, but one word dropped in the middle -
    # so it is not a whole phrase, and the points must say so
    hit, why, how_much = titlescore.phrase_hit(
        "लोग आज इग्नोर क्यों करते हैं", ["लोग इग्नोर क्यों करते हैं"])
    assert 0 < how_much < 1.0, f"a partial match scored {how_much}: {why}"
    scored = titlescore.score("लोग आज इग्नोर क्यों करते हैं", cfg,
                             phrases=["लोग इग्नोर क्यों करते हैं"])
    part = next(p for p in scored["parts"] if p["part"] == "search phrase")
    assert 0 < part["points"] < 35, f"partial earned {part['points']}/35"
    assert "whole phrase" in part["note"], part["note"]
    return f"partial -> {part['points']:.1f}/35 - {part['note'][:44]}"


@check("candidate building is deterministic")
def t_deterministic():
    script = fixture_script()
    first = [r["title"] for r in writer.candidates(None, PHRASES, script)[0]]
    second = [r["title"] for r in writer.candidates(None, PHRASES, script)[0]]
    assert first == second, f"{first} != {second}"
    return f"{len(first)} candidates, same list twice"


# --------------------------------------------------------------- titlescore

@check("the generator clears its own target on a real phrase list")
def t_generator_target():
    script = fixture_script()
    scored, best, _ = writer.candidates(None, PHRASES, script)
    assert scored[0]["total"] >= titlescore.GENERATOR_TARGET, \
        f"best candidate scored {scored[0]['total']}, target {titlescore.GENERATOR_TARGET}"
    assert scored[0]["total"] >= titlescore.SCORE_MIN
    return (f"{best!r} = {scored[0]['total']}/100 "
            f"(gate {titlescore.SCORE_MIN}, target {titlescore.GENERATOR_TARGET})")


@check("a footage noun in the title costs points, and the note names it")
def t_footage_noun_costs_points():
    cfg = config.load()
    clean = titlescore.score("लोग इग्नोर क्यों करते हैं और अकेलेपन का सच", cfg,
                             phrases=PHRASES, footage_words=["फ़ोन"])
    dirty = titlescore.score("लोग इग्नोर क्यों करते हैं और फ़ोन का सच", cfg,
                             phrases=PHRASES, footage_words=["फ़ोन"])
    assert dirty["total"] < clean["total"], (dirty["total"], clean["total"])
    part = next(p for p in dirty["parts"] if "footage" in p["part"])
    assert "फ़ोन" in part["note"], part["note"]
    return f"clean {clean['total']} vs footage noun in title {dirty['total']}"


# ------------------------------------------------------------------ assemble

@check("the description, tags and pinned comment obey the plan's rules")
def t_assembled_fields():
    script = fixture_script()
    topic = script["topic"]
    desc = assemble.description(topic, script, "लोग इग्नोर क्यों करते हैं और अकेलेपन का सच", [])
    first = desc.split("\n")[0]
    assert TOPIC_PHRASE in first[:100], f"the search phrase is not in the first line: {first!r}"
    tags = assemble.tags_field(topic, script)
    assert 10 <= len(tags) <= 15, f"{len(tags)} tag(s)"
    assert not [t for t in tags if t.startswith("#")], "a hashtag is in the tag field"
    assert len(set(tags)) == len(tags), "a tag is repeated"
    assert any(t.isascii() for t in tags), "no English keyword in the tags"
    marks = assemble.hashtags(topic, script)
    assert 3 <= len(marks) <= 5, f"{len(marks)} hashtag(s)"
    assert all(m.startswith("#") and not m.lstrip("#").isascii() for m in marks), marks
    forbidden = [m for m in marks if assemble._found_in_internal(m.lstrip("#"))]
    assert not forbidden, f"an internal word became a hashtag: {forbidden}"
    pinned = assemble.pinned_comment(topic, script, "लोग इग्नोर क्यों करते हैं")
    assert len(pinned.split()) >= 8, f"the pinned comment is only {len(pinned.split())} words"
    assert pinned.rstrip().endswith("?"), pinned
    return f"desc {len(desc)} chars, {len(tags)} tags, {len(marks)} hashtags, pinned {len(pinned.split())} words"


@check("audit passes a good payload and fails a broken one")
def t_audit_both_ways():
    script = fixture_script()
    topic = script["topic"]
    tagged = assemble.tags_field(topic, script)
    desc = assemble.description(topic, script, "लोग इग्नोर क्यों करते हैं और अकेलापन", tagged)
    good = {
        "render_id": TEST_ID, "title_hi": "लोग इग्नोर क्यों करते हैं और अकेलेपन का सच",
        "search_phrase_hi": TOPIC_PHRASE, "description": desc, "tags": tagged,
        "pinned_comment": assemble.pinned_comment(topic, script, TOPIC_PHRASE),
        "hashtags": assemble.hashtags(topic, script), "thumbnail": {"at": 0.0},
    }
    rows = assemble.audit(good)
    failed = [r for r in rows if not r["pass"]]
    assert not failed, f"a good payload failed its own audit: {failed}"

    broken = json.loads(json.dumps(good))
    broken["description"] = "कोई ऐसा वाक्य जिसमें खोज वाक्यांश नहीं है।\n\n#shorts"
    broken["tags"] = [f"tag{i}" for i in range(20)]
    broken["title_hi"] = "ANTAR लाने-बी का सच"
    broken["pinned_comment"] = "हाँ?"
    rows = assemble.audit(broken)
    names = [r["check"] for r in rows if not r["pass"]]
    assert len(names) >= 4, f"only {len(names)} rule(s) fired on a payload that breaks four"
    for needed in ("the search phrase is inside the first 100 characters",
                   "3-5 hashtags in the description",
                   "10-15 keywords in the tag field",
                   "no internal labels in anything public"):
        assert needed in names, f"{needed!r} did not fire: {names}"
    return f"good: all pass; broken: {len(names)} rule(s) fired"


# ------------------------------------------------------------------- end to end

@check("the whole stage runs on a real script and writes its file")
def t_stage_end_to_end():
    cfg = config.load()
    scripts = cfg.path("paths.output") / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    script_path = keep(scripts / f"{TEST_ID}.json")
    script = fixture_script()
    script_path.write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
    keep(harvest.save(cfg, TEST_ID, {"phrases": PHRASES, "sources": [], "note": "test", "when": 0.0}))

    result = run(cfg, TEST_ID)
    keep(result.path)
    payload = result.payload
    assert result.passed, f"the stage failed its own audit: {result.failures()}"
    assert payload["chosen_score"] >= titlescore.GENERATOR_TARGET, payload["chosen_score"]
    assert payload["title_hi"] in [c["title"] for c in payload["candidates"]]
    assert payload["harvest"]["scored_against"], "the phrase list was not recorded"
    assert payload["thumbnail"], "no thumbnail moment"
    back = json.loads(result.path.read_text(encoding="utf-8"))
    assert back["title_hi"] == payload["title_hi"], "the file does not match the run"
    return (f"{result.path.name}: title {payload['chosen_score']}/100, "
            f"{len(payload['candidates'])} candidates, {len(payload['tags'])} tags")


@check("the check suite scores the generated title against the same list")
def t_suite_and_generator_agree():
    cfg = config.load()
    details_path = cfg.path("paths.output") / "details" / f"{TEST_ID}_details.json"
    payload = json.loads(details_path.read_text(encoding="utf-8"))
    bundle = base_bundle("p7wire", script=fixture_script())
    bundle["details"] = payload
    report = run_bundle(bundle, "p7wire")
    title = find(report, "title score")
    assert title.status == PASS, f"the generated title failed the gate: {title.measured} {title.detail}"
    assert payload["chosen_score"] >= titlescore.GENERATOR_TARGET
    assert "details file" in title.detail, title.detail
    phrases, source = suite.title_phrases(bundle, cfg)
    assert phrases == payload["harvest"]["scored_against"], \
        "the suite and the generator are scoring different lists"
    return f"suite {title.measured} on {len(phrases)} phrase(s) from {source}"


@check("without a details file the suite falls back to the topic, not to zero")
def t_suite_falls_back_to_the_topic():
    cfg = config.load()
    bundle = base_bundle("p7fall", script=fixture_script())
    bundle["details"] = None
    phrases, source = suite.title_phrases(bundle, cfg)
    assert phrases and TOPIC_PHRASE in phrases, (phrases, source)
    assert "topic" in source or "harvest" in source, source
    report = run_bundle(bundle, "p7fall")
    title = find(report, "title score")
    assert title.status == PASS, f"the topic's own title failed: {title.measured} {title.detail}"
    return f"{title.measured} on {len(phrases)} phrase(s) from {source}"


@check("the stage refuses to guess when no script exists")
def t_no_script_is_an_error():
    from antar.details import __init__ as details_pkg  # noqa: F401

    class Bare:
        def path(self, key):
            return Path("/nonexistent/antar")

    try:
        run(Bare(), "TEST7_NOTHING")
    except DetailsError as exc:
        assert "script" in str(exc).lower(), str(exc)
        return f"DetailsError: {exc}"
    raise AssertionError("the stage invented a script instead of stopping")


@check("the live harvest's kept phrases still pass the writer's own filter")
def t_kept_phrases_survive_the_writer():
    cfg = config.load()
    path = cfg.path("paths.output") / "details" / "ANTAR_0001_lane-b-pilot_harvest.json"
    if not path.exists():
        return "no live harvest on disk in this workspace - nothing to check"
    saved = json.loads(path.read_text(encoding="utf-8"))
    script_path = cfg.path("paths.output") / "scripts" / "ANTAR_0001_lane-b-pilot.json"
    if not script_path.exists():
        return "the render's script is not on disk - nothing to check"
    script = json.loads(script_path.read_text(encoding="utf-8"))
    vocabulary = harvest.vocabulary_for(script)
    kept = saved.get("phrases") or []
    dropped = [p for p in kept if not harvest._allowed(p, vocabulary)]
    assert not dropped, f"the writer would drop phrases the harvest kept: {dropped[:2]}"
    return f"{len(kept)} kept phrase(s) all survive the writer's filter"


ALL = [
    t_roots, t_off_topic_is_rejected, t_empty_harvest_is_honest, t_harvest_round_trip,
    t_candidates_use_whole_phrases, t_off_topic_never_becomes_a_title,
    t_fragment_never_earns_the_points, t_partial_phrase_earns_part,
    t_kept_phrases_survive_the_writer,
    t_deterministic, t_generator_target, t_footage_noun_costs_points,
    t_assembled_fields, t_audit_both_ways, t_stage_end_to_end,
    t_suite_and_generator_agree, t_suite_falls_back_to_the_topic,
    t_no_script_is_an_error,
]


def clean_up() -> int:
    """Fixtures are removed from the real folders - the workshop stays clean."""
    removed = 0
    for path in WRITTEN:
        try:
            if path.exists():
                path.unlink()
                removed += 1
        except OSError:
            pass
    for extra in ("output/details", "output/scripts"):
        for path in Path(ROOT).joinpath(extra).glob("TEST7_*"):
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def run_all(verbose: bool = True) -> bool:
    RESULTS.clear()
    if verbose:
        print("\nPHASE 7 - details")
    for test in ALL:
        test(verbose)
    shutil.rmtree(Path(ROOT) / "output" / "checks" / "p7wire", ignore_errors=True)
    shutil.rmtree(Path(ROOT) / "output" / "checks" / "p7fall", ignore_errors=True)
    clean_up()
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    if verbose:
        print(f"  phase 7: {passed}/{len(RESULTS)} passed")
    return passed == len(RESULTS)


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
