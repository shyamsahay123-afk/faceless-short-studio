"""
ANTAR - Phase 4 test suite.

Proves the picture half of the engine, with no network and no API key:

  - a text card lands in the 35-45 brightness band, whatever word it carries
  - the card is never pure black and never pure white
  - a clip whose page address names a person is refused before download
  - "clock hands" is not a person, and is not thrown away
  - only portrait, only long enough, never twice in one video
  - the same object coming back in one video gets the same shot back
  - the vault counts a use per VIDEO, not per run
  - holds come from the voice, word for word, and say so when they cannot
  - with no key at all the stage still produces a plan: every beat a card

The stock library is faked. The downloads are real files made by ffmpeg, so
the hashing, the signatures, the probing and the vault are all exercised for
real. The live proof - eight real Pexels clips - is in PHASE4_REPORT.md.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from antar import config                                  # noqa: E402
from antar.picture import card, choose, faces, plan as planner, sources   # noqa: E402
from antar.picture.sources import Candidate               # noqa: E402
from antar.vault import Vault, find_ffmpeg                # noqa: E402

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

_CACHE: dict = {}

SCRIPT = {
    "render_id": "TEST_0004",
    "script": {
        "title_hi": "जाँच",
        "peak_line": 4,
        "closing_echo": "कुछ",
        "beats": [
            {"line_hi": "वो फ़ोन मेज़ पर पड़ा रहता है।", "object_hi": "फ़ोन", "role": "hook"},
            {"line_hi": "तुम उसी मग को देखते रहते हो।", "object_hi": "मग", "role": "build"},
            {"line_hi": "हर बार वही दीवार।", "object_hi": "दीवार", "role": "build"},
            {"line_hi": "वो फ़ोन जो मेज़ पर पड़ा है।", "object_hi": "फ़ोन", "role": "payoff"},
        ],
    },
}


PATTERNS = {
    "a": "testsrc2=size=720x1280:rate=12",
    "b": "smptebars=size=720x1280:rate=12",
    "c": "testsrc=size=720x1280:rate=12",
    "d": "smptehdbars=size=720x1280:rate=12",
    "e": "colorspectrum=size=720x1280:rate=12",
    "k": "color=c=black:size=720x1280:rate=12",
}


SCRIPT4 = {
    "render_id": "TEST_0005",
    "script": {"title_hi": "जाँच", "peak_line": 2,
               # one word per beat, so the two marks below line up with them
               "beats": [{"line_hi": "फ़ोन,", "object_hi": "फ़ोन", "role": "hook"},
                         {"line_hi": "फ़ोन।", "object_hi": "फ़ोन", "role": "payoff"}]},
}


def clip_file(name: str, seconds: float = 4.0, pattern: str = "a") -> Path:
    """
    A real, tiny, portrait mp4 with structure in it.

    Structured on purpose: three flat colour bars have the same perceptual
    signature, so the vault's lookalike rule correctly refused them as repeats
    of each other and half a test video fell back to text cards. That was the
    fixture being unrealistic, not the rule being wrong - but it is worth
    knowing that flat footage defeats a perceptual hash.
    """
    key = f"clip_{name}"
    if key in _CACHE:
        return _CACHE[key]
    ff = find_ffmpeg()
    if not ff:
        raise AssertionError("no ffmpeg available for the fixture")
    folder = Path(tempfile.mkdtemp())
    path = folder / f"{name}.mp4"
    source = PATTERNS.get(pattern or name, PATTERNS["a"])
    subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi",
                    "-i", f"{source}:d={seconds}",
                    "-pix_fmt", "yuv420p", "-t", str(seconds), str(path)],
                   capture_output=True, check=True)
    _CACHE[key] = path
    return path


def candidate(clip_id: str, query: str, *, slug: str = "", seconds: float = 8.0,
              width: int = 720, height: int = 1280) -> Candidate:
    return Candidate(source="pexels", id=clip_id, query=query,
                     file_url=f"https://example.invalid/{clip_id}.mp4",
                     width=width, height=height, duration=seconds,
                     page_url=f"https://www.pexels.com/video/{slug}-{clip_id}/")


def fake_source(candidates_by_query: dict, downloads: dict | None = None):
    """
    A stand-in for sources.search + sources.download.

    downloads maps a candidate key to the file to hand back, so the vault,
    the hashing and the probing all run on real bytes.
    """
    # the signature mirrors the real one, ornament for ornament - a fake that
    # accepts fewer arguments than the thing it stands in for is how a test
    # passes while the real call fails
    def search(service, key, query, per_page=15, min_height=1280,
               prefer_height=1920):
        return list(candidates_by_query.get(query, []))

    return search


def temp_config(folder: Path) -> config.Config:
    raw = json.loads(Path(config.config_path()).read_text(encoding="utf-8"))
    raw["paths"]["output"] = str(folder / "output")
    raw["paths"]["vault"] = str(folder / "vault")
    raw["paths"]["assets"] = str(ROOT / "assets")
    (folder / "vault" / "clips").mkdir(parents=True, exist_ok=True)
    return config.Config(raw, Path(config.config_path()))


# ---------------------------------------------------------------- the card

@check("a text card lands in the brightness band whatever word it carries")
def t_card_brightness():
    cfg = config.load()
    folder = Path(tempfile.mkdtemp())
    readings = []
    for i, word in enumerate(["फ़ोन", "कुर्सी", "घड़ी", "वो फ़ोन जो मेज़ पर पड़ा है"]):
        made = card.build_card(word, folder / f"c{i}.png", cfg)
        readings.append(made.brightness)
        assert 35 <= made.brightness <= 45, \
            f"{word!r} came out at {made.brightness:.1f}, outside 35-45"
    spread = max(readings) - min(readings)
    assert spread < 3, f"the band is {spread:.1f} wide across four words"
    return f"{min(readings):.1f}-{max(readings):.1f} across four words"


@check("a card is never pure black and never pure white")
def t_card_no_extremes():
    from PIL import Image
    cfg = config.load()
    folder = Path(tempfile.mkdtemp())
    made = card.build_card("दीवार", folder / "c.png", cfg)
    with Image.open(made.path) as img:
        grey = img.convert("L")
        histogram = grey.histogram()
    assert histogram[0] < 200, f"{histogram[0]} pixels are pure black"
    assert histogram[255] < 2000, f"{histogram[255]} pixels are pure white"
    return f"black {histogram[0]}px, white {histogram[255]}px"


@check("an empty card is refused rather than drawn blank")
def t_card_refuses_empty():
    cfg = config.load()
    folder = Path(tempfile.mkdtemp())
    try:
        card.build_card("   ", folder / "c.png", cfg)
    except card.CardError as exc:
        assert "word" in str(exc)
        return "refused with a reason"
    raise AssertionError("an empty card was drawn")


# ---------------------------------------------------------------- refusing

@check("a clip about a person is refused, and clock hands are not a person")
def t_people_words():
    caught = [faces.people_words_in(t) for t in
              ("a person touching a cellphone screen",
               "an elderly man looking at a grandfather clock",
               "a woman closing the door",
               "portrait of a girl")]
    assert all(caught), f"some person descriptions got through: {caught}"

    safe = ["close-up of clock hands", "hands of a wall clock",
            "chair and table in a room", "surface with a shadow",
            "hairdresser chair", "a handbag on a chair"]
    missed = [t for t in safe if faces.people_words_in(t)]
    assert not missed, f"these were wrongly treated as people: {missed}"

    # The list leans cautious on purpose. "human resources building" is an
    # office and it gets refused, because the cost of refusing a clip is
    # another search and the cost of letting a person through is a rule broken
    # in a published video. That trade is deliberate and it is asserted here
    # so nobody "fixes" it later by accident.
    assert faces.people_words_in("the human resources building"), \
        "the list stopped being cautious about the word human"
    return "4 descriptions caught, 6 innocent ones left alone, 1 refused on purpose"


@check("the page address is read, so a person is refused before download")
def t_slug_filter():
    slug = faces.slug_words(
        "https://www.pexels.com/video/elderly-man-using-a-stethoscope-8321896/")
    assert slug == "elderly man using a stethoscope", slug

    c = candidate("8321896", "clock on wall", slug=slug)
    chosen, notes = choose.pick([c], seed="x")
    assert chosen is None, "a clip about a man was chosen"
    assert any("person" in n for n in notes), notes
    return notes[0][:64]


@check("the file downloaded is a real 1080x1920 when the clip has one")
def t_file_size_choice():
    ladder = [{"width": w, "height": h, "link": f"u{h}"} for w, h in
              [(360, 640), (540, 960), (720, 1280), (1080, 1920), (1440, 2560), (2160, 3840)]]
    assert sources._pick_file(ladder, 1280)["height"] == 1920, \
        "took a smaller rendition while a 1080x1920 file was on offer"

    small = [{"width": w, "height": h, "link": f"u{h}"} for w, h in
             [(360, 640), (540, 960), (720, 1280)]]
    assert sources._pick_file(small, 1280)["height"] == 1280, \
        "with nothing HD on offer it should take the biggest, not the smallest"

    land = [{"width": 1920, "height": 1080, "link": "x"}] + ladder
    assert sources._pick_file(land, 1280)["height"] == 1920, "landscape was picked"
    assert sources._pick_file([{"width": None, "height": None, "link": "x"}], 1280) is None
    return "1080x1920 first, biggest-of-what-exists as the fallback"


@check("only portrait footage is accepted")
def t_portrait_only():
    portrait = candidate("1", "empty chair")
    landscape = candidate("2", "empty chair", width=1920, height=1080)
    chosen, notes = choose.pick([landscape, portrait], seed="x")
    assert chosen is not None and chosen.id == "1", f"chose {chosen and chosen.id}"
    assert any("landscape" in n for n in notes), notes
    return "landscape refused, portrait kept"


@check("a clip shorter than the floor is refused")
def t_min_seconds():
    short = candidate("1", "empty chair", seconds=1.5)
    long = candidate("2", "empty chair", seconds=9.0)
    chosen, notes = choose.pick([short, long], seed="x", min_seconds=3.0)
    assert chosen is not None and chosen.id == "2"
    assert any("only" in n for n in notes), notes
    return "1.5s refused, 9.0s kept"


@check("the same clip is never taken twice in one video")
def t_not_twice_in_one_video():
    a, b = candidate("1", "empty chair"), candidate("2", "empty chair")
    first, _ = choose.pick([a, b], seed="x")
    second, notes = choose.pick([a, b], seed="x", used_keys={first.key})
    assert second is not None and second.key != first.key, "the same clip came back"
    assert any("already used" in n for n in notes), notes
    return f"{first.key} then {second.key}"


@check("the same script and seed give the same clip every time")
def t_deterministic():
    pool = [candidate(str(i), "empty chair") for i in range(8)]
    first = [choose.pick(pool, seed="seed-a")[0].id for _ in range(3)]
    assert len(set(first)) == 1, f"three runs chose {first}"
    other = [choose.pick(pool, seed=f"seed-{i}")[0].id for i in range(6)]
    assert len(set(other)) > 1, "the seed does nothing, so every video picks the same clip"
    return f"stable on one seed, varied across seeds ({first[0]} vs {other[0]})"


@check("nothing usable is a normal answer, not an error")
def t_nothing_usable():
    chosen, notes = choose.pick([], seed="x")
    assert chosen is None and notes == []
    chosen, notes = choose.pick([candidate("1", "empty chair", width=1920, height=1080)],
                                seed="x")
    assert chosen is None
    return "empty list and all-refused both return None"


# ---------------------------------------------------------------- timing

@check("shot windows come from the voice, word for word, and cover the pauses")
def t_windows_from_voice():
    take = {"word_timings": [
        {"w": "a", "start": 0.0, "end": 0.5},
        {"w": "b", "start": 0.5, "end": 1.0},
        {"w": "c", "start": 1.2, "end": 2.0},
        {"w": "d", "start": 2.0, "end": 3.4},
    ]}
    windows, note = planner.beat_windows(take, ["a b", "c d"], total_seconds=3.4)
    assert windows[0]["start"] == 0.0 and windows[0]["end"] == 1.2, windows
    assert windows[1]["start"] == 1.2 and windows[1]["end"] == 3.4, windows
    assert abs(windows[0]["speech"] - 1.0) < 0.001, windows
    assert abs(windows[1]["speech"] - 2.2) < 0.001, windows
    # the gap between the two lines (1.0 -> 1.2) sits inside the FIRST window,
    # so the shot already on screen covers it and the cut does not drift
    assert abs(sum(w["end"] - w["start"] for w in windows) - 3.4) < 0.001
    assert "word for word" in note, note
    return f"{[ (w['start'], w['end']) for w in windows]} - {note}"


@check("when the word counts disagree the fallback says it is a fallback")
def t_windows_fallback():
    take = {"word_timings": [{"w": "a", "start": 0.0, "end": 0.5}]}
    windows, note = planner.beat_windows(take, ["a b c", "d e f"], total_seconds=6.0)
    assert [w["start"] for w in windows] == [0.0, 3.0], windows
    assert [w["end"] for w in windows] == [3.0, 6.0], windows
    assert "did not line up" in note or "evenly" in note, note
    assert "word for word" not in note, "a fallback was reported as a measurement"
    return note


# ---------------------------------------------------------------- the plan

@check("the vault counts a use per video, not per run")
def t_use_is_per_video():
    folder = Path(tempfile.mkdtemp())
    vault = Vault(folder / "clips", cap_gb=5.0, max_uses=2)
    clip = vault.add(clip_file("once"), source="test")
    vault.record_use(clip.hash, "ANTAR_0001")
    assert vault.get(clip.hash).uses == 1
    vault.record_use(clip.hash, "ANTAR_0001")
    assert vault.get(clip.hash).uses == 1, "a re-run of the same video spent a second use"
    vault.record_use(clip.hash, "ANTAR_0002")
    assert vault.get(clip.hash).uses == 2, "a second video did not count"
    return "same video counted once, second video counted"


@check("a whole plan is built from a fake library, and every beat is covered")
def t_plan_end_to_end():
    folder = Path(tempfile.mkdtemp())
    cfg = temp_config(folder)
    candidates = {
        "smartphone on table": [candidate("11", "smartphone on table", slug="phone on a desk",
                                          seconds=9.0)],
        "coffee mug on table": [candidate("22", "coffee mug on table", slug="cup of coffee",
                                          seconds=8.0)],
        "plain wall shadow": [candidate("33", "plain wall shadow", slug="shadow on a wall",
                                        seconds=6.0)],
    }
    files = {"pexels:11": clip_file("a", pattern="a"),
             "pexels:22": clip_file("b", pattern="b"),
             "pexels:33": clip_file("c", pattern="c")}
    real_download = sources.download
    sources.download = lambda cand, dest, max_mb=25.0: _stage(files[cand.key], dest)
    try:
        built = planner.build_plan(cfg, SCRIPT, source=fake_source(candidates), seed="TEST_0004")
    finally:
        sources.download = real_download

    shots = built["shots"]
    assert len(shots) == 4, f"{len(shots)} shots for 4 beats"
    assert all(s["kind"] == "clip" for s in shots), \
        f"some beats fell back to cards: {[s['kind'] for s in shots]}"
    assert shots[0]["path"] == shots[3]["path"], \
        "the line that comes back to the phone got a different shot"
    assert "on purpose" in " ".join(shots[3]["notes"]), shots[3]["notes"]
    assert len({s["path"] for s in shots}) == 3, "the same clip was used for three objects"
    assert built["totals"]["downloads"] == 3, built["totals"]
    assert all(s["hold"] > 0 for s in shots), [s["hold"] for s in shots]

    # the windows tile the timeline with no gap and no overlap, so the cut can
    # be placed on a frame without drifting against the voice
    assert shots[0]["start"] == 0.0, shots[0]["start"]
    for earlier, later in zip(shots, shots[1:]):
        assert abs(earlier["end"] - later["start"]) < 0.001, \
            f"gap between beat {earlier['index']} and {later['index']}: " \
            f"{earlier['end']} -> {later['start']}"
    assert all(s["speech"] <= s["hold"] + 0.001 for s in shots), \
        [(s["speech"], s["hold"]) for s in shots]
    assert built["totals"]["seconds_covered"] == round(shots[-1]["end"], 2)
    return (f"{built['totals']['clips']} clips from {built['totals']['downloads']} downloads, "
            f"beat 3 echoes beat 0")


@check("a library that hands back people still leaves every beat covered")
def t_plan_refuses_people():
    folder = Path(tempfile.mkdtemp())
    cfg = temp_config(folder)
    candidates = {
        "smartphone on table": [
            candidate("90", "smartphone on table", slug="a person holding a phone", seconds=8.0),
            candidate("91", "smartphone on table", slug="phone on a wooden desk", seconds=8.0),
        ],
        "coffee mug on table": [
            candidate("92", "coffee mug on table", slug="a man drinking tea", seconds=8.0)],
        "plain wall shadow": [],
    }
    files = {"pexels:91": clip_file("d", pattern="d")}
    real_download = sources.download
    sources.download = lambda cand, dest, max_mb=25.0: _stage(files[cand.key], dest)
    try:
        built = planner.build_plan(cfg, SCRIPT, source=fake_source(candidates), seed="x")
    finally:
        sources.download = real_download

    shots = built["shots"]
    assert shots[0]["clip_id"] == "91", f"a clip about a person was used: {shots[0]['clip_id']}"
    assert shots[1]["kind"] == "card", "the beat with only a person on offer was not carded"
    assert shots[2]["kind"] == "card", "an empty library did not fall back to a card"
    assert shots[3]["path"] == shots[0]["path"], "the echo was lost when the first beat waited"
    cards = [s for s in shots if s["kind"] == "card"]
    assert all(Path(s["path"]).exists() for s in cards), "a card was recorded but not drawn"
    assert all("brightness" in " ".join(s["notes"]) for s in cards)
    return f"{built['totals']['clips']} clips, {built['totals']['cards']} cards, no people"


@check("with no key at all the stage still produces a full plan")
def t_plan_offline():
    folder = Path(tempfile.mkdtemp())
    cfg = temp_config(folder)
    built = planner.build_plan(cfg, SCRIPT, source=lambda *a, **k: [], seed="x")
    shots = built["shots"]
    assert len(shots) == 4
    assert built["totals"]["cards"] == 4, built["totals"]
    assert built["totals"]["clips"] == 0
    assert all(Path(s["path"]).exists() for s in shots)
    return "4 beats, 4 cards, nothing downloaded"


@check("a word mark that overruns the sound is owned up to, not fudged")
def t_overrun_is_admitted():
    folder = Path(tempfile.mkdtemp())
    cfg = temp_config(folder)
    voice = {"track": {"seconds": 10.0}, "word_timings": [
        {"w": "a", "start": 0.0, "end": 5.0},
        {"w": "b", "start": 5.0, "end": 10.4},   # the mark runs past the sound
    ]}
    built = planner.build_plan(cfg, SCRIPT4, source=lambda *a, **k: [],
                               voice=voice, seed="x")
    last = built["shots"][-1]
    assert last["speech"] > last["hold"], f"{last['speech']} vs {last['hold']}"
    assert any("past the sound" in n for n in last["notes"]), last["notes"]
    return last["notes"][-1][:70]


@check("the plan survives being written and read back")
def t_plan_round_trip():
    folder = Path(tempfile.mkdtemp())
    cfg = temp_config(folder)
    built = planner.build_plan(cfg, SCRIPT, source=lambda *a, **k: [], seed="x")
    path = planner.save_plan(cfg, built)
    again = json.loads(Path(path).read_text(encoding="utf-8"))
    assert again["render_id"] == built["render_id"]
    assert len(again["shots"]) == len(built["shots"])
    assert again["totals"] == built["totals"]
    assert "timing" in again and again["timing"]
    return f"{path.name}, {len(again['shots'])} shots"


def _stage(source: Path, dest_dir: Path) -> Path:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / source.name
    dest.write_bytes(source.read_bytes())
    return dest


# ---------------------------------------------------------------- the faces

@check("a mostly black clip is refused, and every kept clip carries its light")
def t_black_frame_refused():
    # only a black clip on offer: the beat must fall back to a card, not to a
    # black frame. "No frame mostly black" is a blocking rule - the cheap place
    # to obey it is here, before a grade would have to rescue it.
    folder = Path(tempfile.mkdtemp())
    cfg = temp_config(folder)
    black = {"pexels:1": clip_file("blk", pattern="k")}
    real_download = sources.download
    sources.download = lambda cand, dest, max_mb=25.0: _stage(black[cand.key], dest)
    try:
        built = planner.build_plan(
            cfg, SCRIPT4, seed="x",
            source=fake_source({"smartphone on table": [candidate("1", "smartphone on table",
                                                                 seconds=5.0)]}))
    finally:
        sources.download = real_download
    shot = built["shots"][0]
    assert shot["kind"] == "card", f"a black clip was kept: {shot['kind']}"
    assert any("black" in n for n in shot["notes"]), shot["notes"]
    assert Path(shot["path"]).exists(), "the fallback card was not drawn"

    # and with a real clip on the same list the beat ends as footage, measured
    folder = Path(tempfile.mkdtemp())
    cfg = temp_config(folder)
    files = {"pexels:1": clip_file("blk", pattern="k") if False else black["pexels:1"],
             "pexels:2": clip_file("src", pattern="a")}
    sources.download = lambda cand, dest, max_mb=25.0: _stage(files[cand.key], dest)
    try:
        built = planner.build_plan(
            cfg, SCRIPT4, seed="x",
            source=fake_source({"smartphone on table": [
                candidate("1", "smartphone on table", seconds=5.0),
                candidate("2", "smartphone on table", seconds=5.0)]}))
    finally:
        sources.download = real_download
    shot = built["shots"][0]
    assert shot["kind"] == "clip", "the beat did not take the usable clip"
    assert shot["brightness"] > 30, f"light recorded as {shot['brightness']}"
    assert shot["black_pct"] < 55, f"black {shot['black_pct']}% kept"
    return f"black refused, kept clip light {shot['brightness']:.0f}/255 black {shot['black_pct']:.0f}%"


@check("the face scan says what it is doing, and finds no face in an empty room")
def t_face_scan():
    if not faces.faces_available():
        note = faces.why_unavailable()
        assert note and note != "ready", "an unavailable scan gave no reason"
        return f"scan off ({note[:40]}) and it says so"

    found, at = faces.scan_for_faces(clip_file("ee", seconds=4.0, pattern="e"))
    assert found == 0, f"{found} faces found in a plain grey rectangle at {at}"
    return "0 faces in a plain clip, scanner present"


ALL = [
    t_card_brightness,
    t_card_no_extremes,
    t_card_refuses_empty,
    t_people_words,
    t_file_size_choice,
    t_slug_filter,
    t_portrait_only,
    t_min_seconds,
    t_not_twice_in_one_video,
    t_deterministic,
    t_nothing_usable,
    t_windows_from_voice,
    t_windows_fallback,
    t_use_is_per_video,
    t_plan_end_to_end,
    t_plan_refuses_people,
    t_plan_offline,
    t_plan_round_trip,
    t_black_frame_refused,
    t_overrun_is_admitted,
    t_face_scan,
]


def run_all(verbose: bool = True) -> bool:
    RESULTS.clear()
    if verbose:
        print()
        print("  ANTAR - PHASE 4 SELF TEST")
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
