"""
ANTAR - Phase 3 test suite.

Proves the voice half of the engine, with no network and no API key:

  - the pause before the payoff is placed after the last word of the line
    before it, and is exactly as long as the config says
  - the pause is REAL silence, measured from the produced file, not asserted
    from the plan (this is the test that catches the drone playing through it)
  - the payoff word itself moves with the pause
  - the payoff is found from the end of the script, so a phrase that also
    appears earlier does not steal it
  - the track starts at 0.000s and the loop seam is closed
  - loudness lands on target
  - word timings in the saved file are where the words really are
  - pacing is measured over speech, not over the file, and the band follows

The take used here is synthesised: tone bursts standing in for words, with the
word list deliberately shifted 150ms early to imitate the MP3 encoder padding
that edge-tts shows on every real take. Nothing here touches the network. The
live proof - a real Swara take, measured - is in PHASE3_REPORT.md.
"""

from __future__ import annotations

import copy
import json
import math
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from antar import cli, config                             # noqa: E402
from antar.voice import build as vbuild                   # noqa: E402
from antar.voice import measure as vmeasure               # noqa: E402
from antar.voice import tts                               # noqa: E402

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

RATE = 24000
LEAD = 0.25           # air in front of the first word, as every real take has
BURST = 0.18          # how long a word stands in for
STEP = 0.24           # word to word
LINE_GAP = 0.40       # the silence the voice leaves before the payoff line
TAIL = 0.10
PADDING = 0.15        # what the MP3 adds in front; the word list is shifted by it
WORDS = 90
PAYOFF_INDEX = 60
DECOY_INDEX = 20      # the payoff phrase, said once early on, on purpose

PAYOFF_WORDS = ["वो", "जवाब", "नहीं"]
PAYOFF_LINE = "वो जवाब नहीं देता है।"

_CACHE: dict = {}


def _tone(freq: float, seconds: float, rate: int = RATE) -> list[float]:
    n = int(seconds * rate)
    return [0.5 * math.sin(2 * math.pi * freq * i / rate) for i in range(n)]


def _write_wav(path: Path, samples: list[float], rate: int = RATE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = bytearray()
    for value in samples:
        clipped = max(-1.0, min(1.0, value))
        frames += int(clipped * 32767).to_bytes(2, "little", signed=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(bytes(frames))
    return path


def _texts() -> list[str]:
    """
    Word texts for the fixture.

    The payoff phrase is placed at word 20 as well as at word 60. A real script
    does this by accident; this one does it on purpose, so that finding the
    payoff by matching the first occurrence is caught rather than shipped.
    """
    texts = [f"शब्द{i}" for i in range(WORDS)]
    for offset, word in enumerate(PAYOFF_WORDS):
        texts[DECOY_INDEX + offset] = word
        texts[PAYOFF_INDEX + offset] = word
    return texts


def take() -> tts.Take:
    """A synthetic take that behaves exactly like a real one, minus the network."""
    if "take" in _CACHE:
        return _CACHE["take"]

    samples = [0.0] * int((LEAD + WORDS * STEP + LINE_GAP + TAIL) * RATE)
    words = []
    texts = _texts()
    cursor = LEAD

    def stamp(start: float, duration: float, freq: float) -> None:
        begin = int(start * RATE)
        for i, value in enumerate(_tone(freq, duration)):
            if begin + i < len(samples):
                samples[begin + i] += value

    for i in range(WORDS):
        if i == PAYOFF_INDEX:
            cursor += LINE_GAP
        stamp(cursor, BURST, 180 + (i % 12) * 30)
        words.append(tts.Word(text=texts[i], start=round(cursor - PADDING, 4),
                              duration=BURST))
        cursor += STEP

    path = _write_wav(Path(tempfile.mkdtemp()) / "take.wav", samples)
    _CACHE["take"] = tts.Take(path=path, voice="test", rate="+0%", pitch="+0Hz",
                              seconds=len(samples) / RATE, words=words,
                              characters=len(PAYOFF_LINE) * 4, seconds_to_generate=0.0)
    return _CACHE["take"]


def built(sub_bass: bool = True) -> vbuild.Built:
    key = f"built_{sub_bass}"
    if key not in _CACHE:
        cfg = config.load()
        out = Path(tempfile.mkdtemp()) / "track.wav"
        _CACHE[key] = vbuild.build(take(), out, cfg, payoff_text=PAYOFF_LINE, sub_bass=sub_bass)
    return _CACHE[key]


def synth_config(output: Path) -> config.Config:
    """The real config with its output paths redirected into a temp folder."""
    raw = json.loads(Path(config.config_path()).read_text(encoding="utf-8"))
    raw["paths"]["output"] = str(output)
    raw["paths"]["vault"] = str(output / "vault")
    (output / "vault").mkdir(parents=True, exist_ok=True)
    return config.Config(raw, Path(config.config_path()))


# ---------------------------------------------------------------- alignment

@check("word times are aligned to the audio, not the synthesiser")
def t_align():
    cfg = config.load()
    plan = vbuild.plan(take(), PAYOFF_LINE, cfg)
    assert abs(plan["word_offset"] - PADDING) < 0.02, \
        f"expected a {PADDING*1000:.0f}ms shift, got {plan['word_offset']*1000:.0f}ms"
    assert abs(plan["trim"] - (LEAD - vbuild.PREROLL)) < 0.02, \
        f"expected a trim of about {LEAD - vbuild.PREROLL:.3f}s, got {plan['trim']:.3f}s"
    return f"shifted {plan['word_offset']*1000:+.0f}ms, trimmed {plan['trim']*1000:.0f}ms"


@check("the pause starts just after the last word of the previous line")
def t_pause_after_last_word():
    cfg = config.load()
    plan = vbuild.plan(take(), PAYOFF_LINE, cfg)
    words, index = take().words, plan["payoff_index"]
    prev_end = words[index - 1].start + words[index - 1].duration + plan["word_offset"] - plan["trim"]
    assert abs(plan["cut_at"] - (prev_end + vbuild.TAIL_AIR)) < 0.03, \
        (f"the pause starts at {plan['cut_at']:.3f}s but the last word ends at "
         f"{prev_end:.3f}s - leftover audio is left playing after the pause")
    assert plan["natural_gap"] > 0.1, "the fixture has no natural gap to replace"
    return f"pause starts at {plan['cut_at']:.3f}s, previous word ends at {prev_end:.3f}s"


@check("the pause is exactly as long as the config says")
def t_pause_length():
    cfg = config.load()
    plan = vbuild.plan(take(), PAYOFF_LINE, cfg)
    want = float(cfg["pacing.silence_before_payoff"])
    got = plan["payoff_at"] - plan["cut_at"]
    assert abs(got - want) < 0.001, f"pause is {got:.3f}s, config says {want:.3f}s"
    return f"{got:.2f}s"


@check("the payoff word itself moves with the pause")
def t_payoff_word_moves():
    cfg = config.load()
    plan = vbuild.plan(take(), PAYOFF_LINE, cfg)
    index = plan["payoff_index"]
    start = plan["aligned_words"][index]
    assert abs(start - plan["payoff_at"]) < 0.005, (
        f"the payoff word is timed at {start:.3f}s but the pause ends at "
        f"{plan['payoff_at']:.3f}s - the word the pause was built for is "
        f"{(plan['payoff_at']-start)*1000:.0f}ms early")
    return f"payoff word at {start:.3f}s, pause ends at {plan['payoff_at']:.3f}s"


@check("the word before the pause does not move")
def t_word_before_pause():
    cfg = config.load()
    plan = vbuild.plan(take(), PAYOFF_LINE, cfg)
    index = plan["payoff_index"]
    end = plan["aligned_words"][index - 1] + take().words[index - 1].duration
    gap = plan["cut_at"] - end
    assert 0.0 <= gap < 0.06, f"the line before the pause ends {gap*1000:.0f}ms from the cut"
    return f"ends {gap*1000:.0f}ms before the pause"


# ---------------------------------------------------------------- finding it

@check("the payoff is found from the end of the script, not the start")
def t_payoff_from_end():
    index = vbuild.payoff_word_index(take(), PAYOFF_LINE)
    assert index == PAYOFF_INDEX, (
        f"found the payoff at word {index}, expected {PAYOFF_INDEX} - the "
        f"sentence also appears earlier in this fixture and the first match won")
    return f"word {index} of {take().word_count}"


@check("a script with no payoff line falls back to the last words")
def t_payoff_fallback():
    index = vbuild.payoff_word_index(take(), "")
    assert index == take().word_count - 3, f"expected {take().word_count-3}, got {index}"
    return f"word {index} - the last three are the payoff"


@check("the pause goes in front of the line the writer named")
def t_payoff_line_from_peak_line():
    beats = [{"line_hi": f"लाइन {i}", "role": "build"} for i in range(1, 9)]
    beats[7] = {"line_hi": "तगड़ी लाइन", "role": "payoff"}

    got, how = cli._payoff_line({"peak_line": 8}, beats)
    assert got == "तगड़ी लाइन", f"peak_line 8 gave {got!r}"
    assert "peak_line" in how

    got, how = cli._payoff_line({"peak_line": "लाइन 3"}, beats)
    assert got == "लाइन 3", f"a named line gave {got!r}"

    got, how = cli._payoff_line({}, beats)
    assert got == "तगड़ी लाइन", f"the payoff role gave {got!r}"

    plain = [{"line_hi": f"लाइन {i}", "role": "build"} for i in range(1, 9)]
    got, how = cli._payoff_line({}, plain)
    assert got == "लाइन 8", f"the fallback gave {got!r}"

    assert cli._payoff_line({}, [])[0] == ""
    return "peak_line, named line, payoff role and fallback all land"


# ---------------------------------------------------------------- the track

@check("the track starts with the first word at 0.000s")
def t_starts_at_zero():
    m = vmeasure.measure(built().path)
    assert m.lead_silence <= 0.02, f"the track starts at {m.lead_silence:.3f}s"
    assert m.envelope_start <= 0.05, f"the sample envelope starts at {m.envelope_start:.3f}s"
    return f"{m.lead_silence:.3f}s of lead"


@check("the pause is real silence in the finished file")
def t_pause_is_silent():
    b = built()
    m = vmeasure.measure(b.path)
    assert m.quiet_seconds >= b.silence_seconds - 0.05, (
        f"only {m.quiet_seconds:.2f}s of true silence was found where "
        f"{b.silence_seconds:.2f}s was planned - something is playing through "
        f"the pause")
    ends_at = m.quiet_at + m.quiet_seconds
    assert abs(ends_at - b.payoff_at) <= 0.20, (
        f"the silence runs {m.quiet_at:.2f}-{ends_at:.2f}s but the payoff lands "
        f"at {b.payoff_at:.2f}s - the pause is in the wrong place")
    return f"{m.quiet_seconds:.2f}s of silence ending at {ends_at:.2f}s"


@check("the pause stays silent with the sub-bass switched off")
def t_pause_without_sub_bass():
    b = built(sub_bass=False)
    m = vmeasure.measure(b.path)
    assert m.quiet_seconds >= b.silence_seconds - 0.05, \
        f"only {m.quiet_seconds:.2f}s of silence found without the sub-bass"
    return f"{m.quiet_seconds:.2f}s"


@check("the sub-bass is synthesised, and it stops for the pause")
def t_sub_bass():
    import subprocess
    import numpy as np
    from antar import config as _config

    cfg = _config.load()
    hz = int(cfg["audio.sub_bass_hz"])
    assets = list((ROOT / "assets").rglob("*.mp3")) + list((ROOT / "assets").rglob("*.wav"))
    assert not assets, f"the sub-bass must be synthesised, found audio assets: {assets}"

    b = built()
    ff = vmeasure.ffmpeg()
    raw = subprocess.run([ff, "-v", "error", "-i", str(b.path), "-af", "lowpass=f=100",
                          "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True).stdout
    samples = np.frombuffer(raw, dtype=np.float32)

    def rms(t0: float, t1: float) -> float:
        chunk = samples[int(t0 * 16000):int(t1 * 16000)]
        return float(np.sqrt((chunk.astype(np.float64) ** 2).mean())) if chunk.size else 0.0

    speech = rms(5.0, 8.0)
    assert speech > 10 ** (-35 / 20), \
        f"there is no low end under the speech ({20*math.log10(max(speech, 1e-12)):.1f}dB) - the sub-bass is missing"

    pause = rms(b.payoff_at - b.silence_seconds + 0.10, b.payoff_at - 0.10)
    assert pause < 10 ** (-70 / 20), (
        f"the low end is still playing inside the pause "
        f"({20*math.log10(max(pause, 1e-12)):.1f}dB against {20*math.log10(speech):.1f}dB "
        f"under the speech) - the drone fills the one moment the video is built around")
    return (f"{hz}Hz at {20*math.log10(speech):.1f}dB under the speech, "
            f"{20*math.log10(max(pause, 1e-12)):.0f}dB inside the pause")


@check("the voice band alone decides where the speech starts and ends")
def t_drone_cannot_mask_the_measurement():
    """
    A drone running under a quiet file must not be able to pass off dead air as
    sound or sound as dead air. The lead and tail are read above 200Hz only.
    """
    import numpy as np
    path = Path(tempfile.mkdtemp()) / "masked.wav"
    samples = [0.0] * int(0.5 * RATE)
    samples += _tone(400, 1.0)
    samples += [0.0] * int(0.6 * RATE)
    samples += [0.05 * math.sin(2 * math.pi * 45 * i / RATE) for i in range(int(1.0 * RATE))]
    _write_wav(path, samples)

    m = vmeasure.measure(path)
    assert m.lead_silence >= 0.45, f"the drone was mistaken for the start of the voice ({m.lead_silence:.2f}s)"
    assert m.tail_silence >= 0.55, f"the drone hid {m.tail_silence:.2f}s of silence at the end"
    return f"lead {m.lead_silence:.2f}s, tail {m.tail_silence:.2f}s, drone ignored"


@check("the dead air after the last word is cut off")
def t_tail_is_cut():
    b = built()
    m = vmeasure.measure(b.path)
    assert m.tail_silence <= 0.08, (
        f"the track ends {m.tail_silence:.2f}s after the voice stops - the video "
        f"sits in silence before it loops")
    return f"{m.tail_silence:.3f}s of air after the voice"


@check("the loop seam is closed")
def t_loop_seam():
    m = vmeasure.measure(built().path)
    cfg = config.load()
    limit = float(cfg["thresholds"]["loop_seam_max_seconds"])
    assert m.tail_silence <= limit, f"tail is {m.tail_silence:.3f}s, limit {limit}s"
    return f"{m.tail_silence:.3f}s of tail"


@check("loudness lands on target")
def t_loudness():
    cfg = config.load()
    target = float(cfg["audio.target_lufs"])
    tolerance = float(cfg["audio.lufs_tolerance"])
    m = vmeasure.measure(built().path)
    assert abs(m.lufs - target) <= tolerance, f"{m.lufs:.1f} LUFS against {target}"
    assert m.peak_db <= -0.9, f"the peak sits at {m.peak_db:.1f}dBFS, the ceiling is -1.0"
    return f"{m.lufs:.1f} LUFS, peak {m.peak_db:.1f}dB"


@check("the encoder's padding is reported as a number, not a warning")
def t_encoder_padding():
    m = vmeasure.measure_words(take())
    assert m.encoder_padding is not None and abs(m.encoder_padding - PADDING) < 0.02, \
        f"padding read as {m.encoder_padding}"
    assert not m.notes, f"expected no warnings on a clean take, got {m.notes}"
    assert any("padding" in line for line in m.lines())
    return f"{m.encoder_padding*1000:.0f}ms, no warnings raised"


# ---------------------------------------------------------------- pacing

@check("pacing is measured over speech, not over the file")
def t_pacing_over_speech():
    t = take()
    over_speech = t.words_per_second
    over_file = t.word_count / t.seconds
    assert t.speech_seconds < t.seconds, "the fixture has no front padding to exclude"
    assert over_speech > over_file, "counting the padding as speech inflates the rate"
    return (f"{over_speech:.3f} w/s over speech against {over_file:.3f} w/s "
            f"over the file - {(over_speech/over_file - 1)*100:.1f}% apart")


@check("the word band follows the measured voice and the target length")
def t_band_follows_the_voice():
    cfg = config.load()
    wps = float(cfg["pacing.words_per_second"])
    overhead = float(cfg["pacing.silence_before_payoff"]) + float(cfg["pacing.loop_gap"])
    low, high = cfg["pacing.band_words"]
    assert low == round(wps * (30 - overhead)), f"band floor {low}, expected {round(wps*(30-overhead))}"
    assert high == round(wps * (40 - overhead)), f"band ceiling {high}, expected {round(wps*(40-overhead))}"
    assert cfg["pacing.render_floor_words"] < low < high < cfg["pacing.render_ceiling_words"]
    return f"{low}-{high} words for a 30-40s track at {wps} w/s"


@check("the synthesiser is asked for word timings, not sentence timings")
def t_word_boundary_required():
    source = (ROOT / "antar" / "voice" / "tts.py").read_text(encoding="utf-8")
    assert 'boundary="WordBoundary"' in source, (
        "edge-tts defaults to SentenceBoundary and then returns no word timings "
        "at all - the take arrives with audio and nothing else")
    return "boundary=WordBoundary"


# ---------------------------------------------------------------- end to end

@check("the whole voice stage runs and proves itself")
def t_end_to_end():
    out = Path(tempfile.mkdtemp())
    cfg = synth_config(out)

    texts = _texts()
    beats = [{"line_hi": f"शब्द{i}", "object_hi": "x", "role": "build"}
             for i in range(WORDS)]
    beats[PAYOFF_INDEX] = {"line_hi": PAYOFF_LINE, "object_hi": "x", "role": "payoff"}
    script = {"title_hi": "जाँच", "peak_line": PAYOFF_INDEX + 1,
              "closing_echo": texts[0], "beats": beats}
    (out / "scripts").mkdir(parents=True, exist_ok=True)
    (out / "scripts" / "TEST_0001.json").write_text(
        json.dumps({"render_id": "TEST_0001", "script": script}, ensure_ascii=False),
        encoding="utf-8")

    real_speak = tts.speak
    fixture = take()

    def fake_speak(text, path, voice="", rate="", pitch=""):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fixture.path.read_bytes())
        return tts.Take(path=path, voice=voice, rate=rate, pitch=pitch,
                        seconds=fixture.seconds, words=list(fixture.words),
                        characters=len(text), seconds_to_generate=0.0)

    tts.speak = fake_speak
    try:
        code = cli.cmd_voice(cfg, [])
    finally:
        tts.speak = real_speak

    saved = json.loads((out / "audio" / "TEST_0001_audio.json").read_text(encoding="utf-8"))
    failures = [c["check"] for c in saved["checks"] if not c["pass"]]
    assert code == 0, f"the stage returned {code}; failing checks: {failures}"
    assert len(saved["word_timings"]) == WORDS, "the word list lost words on the way out"
    assert saved["word_timings"][0]["start"] <= 0.03, \
        f"the first word is saved at {saved['word_timings'][0]['start']}s"
    assert saved["track"]["lead_silence"] <= 0.02

    assert vbuild.payoff_word_index(fixture, PAYOFF_LINE) == PAYOFF_INDEX, \
        "the stage picked the wrong payoff line"
    after = saved["word_timings"][PAYOFF_INDEX]["start"]
    assert abs(after - saved["track"]["payoff_at"]) < 0.01, (
        f"the file says the payoff is at {saved['track']['payoff_at']:.3f}s but "
        f"the word timing says {after:.3f}s - the timings and the audio disagree")
    return f"5 checks passed, payoff word saved at {after:.3f}s"


ALL = [
    t_align,
    t_pause_after_last_word,
    t_pause_length,
    t_payoff_word_moves,
    t_word_before_pause,
    t_payoff_from_end,
    t_payoff_fallback,
    t_payoff_line_from_peak_line,
    t_starts_at_zero,
    t_pause_is_silent,
    t_pause_without_sub_bass,
    t_sub_bass,
    t_drone_cannot_mask_the_measurement,
    t_tail_is_cut,
    t_loop_seam,
    t_loudness,
    t_encoder_padding,
    t_pacing_over_speech,
    t_band_follows_the_voice,
    t_word_boundary_required,
    t_end_to_end,
]


def run_all(verbose: bool = True) -> bool:
    RESULTS.clear()
    if verbose:
        print()
        print("  ANTAR - PHASE 3 SELF TEST")
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
