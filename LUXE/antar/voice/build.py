"""
ANTAR - building the audio track.

What the track is made of, in order:

    [ 20ms of air ]               kept so the first word is not clipped
    [ the first word ]            lands at t = 0.000
    [ the take ]
    [ 0.85s of dead silence ]     placed immediately before the payoff line,
                                  cut to near-silence, never a hard zero
    [ 45Hz sub-bass ]             under the whole thing, synthesised here
    [ 50ms fade out ]             so the loop seam is inaudible

The synthesiser puts about a quarter of a second of dead air in front of the
first word. Every run. That dead air is trimmed here, because the decision to
stay or swipe happens inside the first second and a quarter of it cannot be
spent on nothing.

Everything is synthesised in Python and ffmpeg. There is no assets/sounds
folder and there never will be.

The payoff silence is found from the word timings, not guessed: the tool takes
the start time of the payoff line's first word and cuts a hole immediately
before it. The trim offset is subtracted, because the hole has to be cut in
the trimmed audio, not in the original.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .. import log
from . import measure as measure_mod
from .tts import Take

PREROLL = 0.02          # seconds of air kept in front of the first word
TAIL_AIR = 0.02         # seconds of air kept after the last word before the pause


class BuildError(RuntimeError):
    """The track could not be assembled."""


@dataclass
class Built:
    path: Path
    take_path: Path
    seconds: float = 0.0
    trim: float = 0.0
    payoff_at: float = 0.0
    silence_seconds: float = 0.0
    quiet_at: float = 0.0
    sub_bass_hz: int = 45
    fade_ms: int = 50
    notes: list[str] = field(default_factory=list)


def _run(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or "").strip().splitlines()[-6:]
        raise BuildError("ffmpeg failed:\n  " + "\n  ".join(tail))


def payoff_word_index(take: Take, payoff_text: str) -> int:
    """
    Find which word in the take begins the payoff line.

    Walked by matching the payoff line's first words against the spoken words.
    Falls back to three words from the end, which is where the payoff lives.
    Returns an index, never a time, so the same logic survives a change of
    timing source.
    """
    if not take.words:
        return -1

    target = (payoff_text or "").strip().split()
    if not target:
        return max(0, len(take.words) - 3)

    needle = [w.strip("।,.!?") for w in target[:3] if w.strip("।,.!?")]
    if not needle:
        return max(0, len(take.words) - 3)

    spoken = [w.text.strip("।,.!?") for w in take.words]

    # Walked BACKWARDS. The payoff sits at the end of the script by design, and
    # a phrase like "वो फ़ोन" can easily appear earlier in the build. Taking the
    # first match would put the pause in front of the wrong line.
    for i in range(len(spoken) - 1, -1, -1):
        if spoken[i] != needle[0]:
            continue
        if len(needle) < 2 or (i + 1 < len(spoken) and spoken[i + 1] == needle[1]):
            return i
    return max(0, len(take.words) - 3)


def align(take: Take, ff: str) -> tuple[float, float]:
    """
    Line the word timings up with the audio, and work out how much dead air to
    cut from the front.

    Returns (trim, word_offset).

    The synthesiser reports its first word at one time and the sound actually
    begins at another, about 150ms later, because the MP3 carries encoder
    padding. The samples are the truth. Every word time is shifted by the
    difference so that word times and audio agree, and the front is trimmed so
    the first word lands at 0.000.

    Getting this wrong is not cosmetic: an uncorrected offset puts the payoff
    silence in the wrong place and starts the video a quarter-second late.
    """
    if not take.words:
        return 0.0, 0.0

    audible_onset = measure_mod.onset(take.path)
    if audible_onset <= 0.0:
        # nothing audible found; keep the raw timings rather than inventing a shift
        audible_onset = take.words[0].start

    word_offset = audible_onset - take.words[0].start
    trim = max(0.0, audible_onset - PREROLL)
    return trim, word_offset


def plan(take: Take, payoff_text: str, config, ff: str = "") -> dict:
    """
    Work out the whole edit before touching a single sample.

    The pause is INSERTED, not carved out of the gap that happens to be there.

    An earlier version cut a hole starting where the previous line ended and
    ended it 0.35s before the payoff, which left the tail of the old audio
    playing after the silence and put the pause in the wrong place. The pause
    is the most important moment in the video and it is placed exactly:

        ... last word of the line before
        [20ms of air]                     <- the cut
        [0.85s of true silence]           <- inserted, synthesised here
        the payoff line                   <- starts the instant the silence ends

    The word times in the result are already corrected twice: once by the
    MP3 padding offset, once by the front trim, and once more by the length of
    the live silence. What comes out of here is where every word will be in the
    finished track.
    """
    silence = float(config.get("pacing.silence_before_payoff", 0.85))
    loop_gap = float(config.get("pacing.loop_gap", 0.05))

    trim, word_offset = align(take, ff or "")

    # word times in the trimmed audio
    trimmed_words = [(w.text, w.start + word_offset - trim, w.duration) for w in take.words]

    index = payoff_word_index(take, payoff_text)
    if 0 <= index < len(trimmed_words):
        payoff_source = max(0.0, trimmed_words[index][1])
        if index > 0:
            prev_text, prev_start, prev_dur = trimmed_words[index - 1]
            prev_end = prev_start + prev_dur
        else:
            prev_end = 0.0
    else:
        payoff_source = trimmed_words[-1][1] if trimmed_words else 0.0
        prev_end = trimmed_words[-2][1] + trimmed_words[-2][2] if len(trimmed_words) > 1 else 0.0

    cut_at = max(0.0, min(prev_end + TAIL_AIR, payoff_source))
    payoff_at = cut_at + silence
    shift = payoff_at - payoff_source
    natural_gap = max(0.0, payoff_source - prev_end)

    aligned_words = []
    for i, (_text, start, _dur) in enumerate(trimmed_words):
        # i >= index, not i > index: the payoff word is the first word after
        # the inserted pause and has to move with the words behind it. Leaving
        # it out puts the one word the pause was built for 86ms early.
        aligned_words.append(round(start + (shift if i >= index else 0.0), 4))

    if trimmed_words:
        last = max(start + dur for _text, start, dur in trimmed_words) + shift
    else:
        last = 0.0

    return {
        "trim": trim,
        "word_offset": word_offset,
        "aligned_words": aligned_words,
        "payoff_index": index,
        "payoff_source": payoff_source,
        "prev_word_ends": prev_end,
        "natural_gap": natural_gap,
        "cut_at": cut_at,
        "payoff_at": payoff_at,
        "last_word_ends": last,
        "shift": shift,
        "silence": silence,
        "loop_gap": loop_gap,
        "sub_bass_hz": int(config.get("audio.sub_bass_hz", 45)),
        "target_lufs": float(config.get("audio.target_lufs", -14.0)),
    }


def build(take: Take, out_path: Path, config, payoff_text: str = "",
          sub_bass: bool = True) -> Built:
    """Assemble the finished track and return what was done to it."""
    ff = measure_mod.ffmpeg()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    steps = plan(take, payoff_text, config, ff=ff)
    built = Built(path=out_path, take_path=take.path, trim=steps["trim"],
                  payoff_at=steps["payoff_at"], silence_seconds=steps["silence"],
                  quiet_at=steps["payoff_at"] - steps["silence"],
                  sub_bass_hz=steps["sub_bass_hz"],
                  fade_ms=int(steps["loop_gap"] * 1000))

    if abs(steps["word_offset"]) > 0.01:
        built.notes.append(
            f"word timings shifted {steps['word_offset']*1000:+.0f}ms to match the audio - "
            f"the synthesiser reports word positions before the MP3 padding")
    if steps["trim"] > 0.005:
        built.notes.append(
            f"trimmed {steps['trim']*1000:.0f}ms of dead air from the front - "
            f"the synthesiser pads every take")
    else:
        built.notes.append("nothing to trim from the front")
    if steps["natural_gap"] > 0.005:
        built.notes.append(
            f"the voice left {steps['natural_gap']*1000:.0f}ms of its own silence before "
            f"the payoff - replaced, so the pause is exactly {steps['silence']:.2f}s")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        trimmed = tmp / "trimmed.wav"

        # ---------------------------------------------- 1. trim the front
        _run([ff, "-v", "error", "-y", "-i", str(take.path),
              "-ss", f"{steps['trim']:.4f}", "-ar", "48000", "-ac", "1", str(trimmed)])

        # ---------------------------------------------- 2. the death silence
        if steps["cut_at"] > 0.3:
            # asetpts=PTS-STARTPTS resets each segment to start at zero. It is
            # the only timebase-safe choice: N/SR/TB assumes a timebase of
            # 1/sample-rate, and an MP3 does not have one, so the segments get
            # scaled and the silence stops being silent.
            chain = (
                f"[0:a]atrim=0:{steps['cut_at']:.4f},asetpts=PTS-STARTPTS[a];"
                f"anullsrc=r=48000:cl=mono:d={steps['silence']:.4f}[s];"
                f"[0:a]atrim={steps['payoff_source']:.4f},asetpts=PTS-STARTPTS[b];"
                f"[a][s][b]concat=n=3:v=0:a=1[out]"
            )
            _run([ff, "-v", "error", "-y", "-i", str(trimmed),
                  "-filter_complex", chain, "-map", "[out]",
                  "-ar", "48000", "-ac", "1", str(tmp / "spaced.wav")])
            built.notes.append(
                f"{steps['silence']:.2f}s of dead silence inserted at "
                f"{steps['cut_at']:.3f}s, the payoff lands at {steps['payoff_at']:.3f}s")
        else:
            _run([ff, "-v", "error", "-y", "-i", str(trimmed),
                  "-ar", "48000", "-ac", "1", str(tmp / "spaced.wav")])
            built.notes.append("no usable payoff position - silence not inserted")

        # ---------------------------------------------- 3. sub-bass and loudness
        #
        # The bass is muted through the payoff silence. Without this the hole
        # is not silent at all - the drone fills it, and the single most
        # important moment in the video disappears. It is ramped rather than
        # switched, because a hard cut on a sine wave clicks.
        inputs = ["-i", str(tmp / "spaced.wav")]
        chain: list[str] = []
        if sub_bass:
            inputs += ["-f", "lavfi", "-i",
                       f"sine=frequency={steps['sub_bass_hz']}:sample_rate=48000"]
            bass_level = float(config.get("audio.sub_bass_level", 0.035))

            if steps["cut_at"] > 0.3 and steps["silence"] > 0.1:
                # The ramps sit OUTSIDE the pause. Fading inside it would eat
                # 80ms off each end and leave 0.70s of audible silence where
                # the design asks for 0.85.
                start = steps["cut_at"]
                end = steps["payoff_at"]
                ramp = 0.03
                envelope = (
                    f"if(lt(t,{start - ramp:.4f}),1,"
                    f"if(lt(t,{start:.4f}),1-(t-{start - ramp:.4f})/{ramp},"
                    f"if(lt(t,{end:.4f}),0,"
                    f"if(lt(t,{end + ramp:.4f}),(t-{end:.4f})/{ramp},1))))"
                )
                chain.append(
                    f"[1:a]volume={bass_level},afade=t=in:st=0:d=0.8,"
                    f"volume='{envelope}':eval=frame[bass]")
                # eval=frame is not optional. The volume filter evaluates its
                # expression once and reuses that value for the whole file by
                # default, so without it the drone plays straight through the
                # pause and the most important moment in the video is filled
                # with a hum that no measurement catches.
                built.notes.append(
                    f"sub-bass muted from {start:.2f}s to {end:.2f}s, "
                    f"ramped over {ramp*1000:.0f}ms before and after - the pause is silent")
            else:
                chain.append(f"[1:a]volume={bass_level},afade=t=in:st=0:d=0.8[bass]")

            chain.append("[0:a][bass]amix=inputs=2:duration=first:dropout_transition=0[mix]")
            chain.append(f"[mix]loudnorm=I={steps['target_lufs']}:TP=-1.0:LRA=8[out]")
            built.notes.append(
                f"{steps['sub_bass_hz']}Hz sub-bass at {bass_level:.3f} - synthesised, no asset file")
        else:
            chain.append(f"[0:a]loudnorm=I={steps['target_lufs']}:TP=-1.0:LRA=8[out]")

        _run([ff, "-v", "error", "-y", *inputs,
              "-filter_complex", ";".join(chain), "-map", "[out]",
              "-ar", "48000", "-ac", "1", str(tmp / "mixed.wav")])

        # ---------------------------------------------- 4. close the loop seam
        #
        # The take carries about three quarters of a second of dead air after
        # the last word. Left in, the video ends and sits in silence before it
        # loops - the seam the whole format depends on, broken. The track is
        # cut to just past the last word and the last 50ms is faded, so the
        # end of the file is silent and the start of the file is the first word.
        total = measure_mod.measure(tmp / "mixed.wav").seconds
        _voice_start, voice_end = measure_mod.voice_bounds(tmp / "mixed.wav")
        end_at = min(total, (voice_end if voice_end > 0 else steps["last_word_ends"])
                     + steps["loop_gap"])
        fade_start = max(0.0, end_at - steps["loop_gap"])
        _run([ff, "-v", "error", "-y", "-i", str(tmp / "mixed.wav"),
              "-t", f"{end_at:.4f}",
              "-af", f"afade=t=out:st={fade_start:.4f}:d={steps['loop_gap']:.4f}",
              "-ar", "48000", "-ac", "1", str(out_path)])

        built.seconds = end_at
        trimmed = total - end_at
        if trimmed > 0.05:
            built.notes.append(
                f"cut {trimmed*1000:.0f}ms of dead air off the end - the file stops "
                f"where the voice stops, measured, so the loop restarts on the last word")
        built.notes.append(
            f"{steps['loop_gap']*1000:.0f}ms fade out at {fade_start:.3f}s - the loop seam")

    if not out_path.exists():
        raise BuildError("the track was not written")

    log.ok(f"track built: {built.seconds:.2f}s, first word at 0.000s, "
           f"payoff at {built.payoff_at:.2f}s")
    return built
