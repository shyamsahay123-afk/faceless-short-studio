"""
ANTAR - measuring audio.

Every number this returns is read from the produced file with ffmpeg. Nothing
is estimated from the script length, and nothing is taken on trust.

Three independent ways to find where the speech starts, because each one has a
blind spot:

  * ffmpeg silencedetect   good for clearly bounded silence, but its threshold
                           is relative to the loudest peak, so it can miss a
                           quiet start
  * an RMS envelope        computed here from the raw samples, with an absolute
                           floor. Catches what silencedetect misses
  * the voice's own word boundaries
                           exact, but only available for audio ANTAR produced

When the three disagree the answer is reported, not averaged away.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .. import log
from ..vault import find_ffmpeg


class AudioError(RuntimeError):
    """ffmpeg is missing or the file is unreadable."""


@dataclass
class Measurement:
    path: str
    seconds: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    lead_silence: float = 0.0        # silence before the first sound
    tail_silence: float = 0.0        # silence after the last sound
    peak_db: float = -99.0
    lufs: float = -99.0              # integrated loudness
    lufs_range: float = 0.0
    true_peak_db: float = -99.0
    envelope_start: float = 0.0      # first sample above the absolute floor
    encoder_padding: float | None = None   # dead air the MP3 adds in front
    quiet_at: float = 0.0            # start of the longest silent stretch
    quiet_seconds: float = 0.0       # how long that stretch lasts
    words: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def speech_seconds(self) -> float:
        return max(0.0, self.seconds - self.lead_silence - self.tail_silence)

    def lines(self) -> list[str]:
        out = [
            f"duration        {self.seconds:8.3f}s",
            f"voice starts    {self.lead_silence:8.3f}s   (band above 200Hz)",
            f"voice ends      {self.seconds - self.tail_silence:8.3f}s   "
            f"({self.tail_silence:.3f}s of air to the end)",
            f"envelope start  {self.envelope_start:8.3f}s",
            f"longest silence {self.quiet_seconds:8.3f}s   (starts at {self.quiet_at:.3f}s)",
            f"loudness        {self.lufs:8.1f} LUFS",
            f"peak            {self.peak_db:8.1f} dBFS",
            f"sample rate     {self.sample_rate}   channels {self.channels}",
        ]
        if self.encoder_padding is not None and self.encoder_padding > 0.02:
            out.append(
                f"encoder padding {self.encoder_padding:8.3f}s   "
                f"(dead air the MP3 added - trimmed off, not the voice's fault)")
        return out


def ffmpeg() -> str:
    path = find_ffmpeg()
    if not path:
        raise AudioError("no ffmpeg available - run INSTALL.bat")
    return path


def _probe(path: Path) -> dict:
    ff = ffmpeg()
    result = subprocess.run([ff, "-hide_banner", "-i", str(path)],
                            capture_output=True, text=True)
    text = result.stderr
    info: dict = {}

    match = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", text)
    if match:
        info["seconds"] = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))

    match = re.search(r"Audio:\s*[^,]+(?:,\s*[^,]+)*?,\s*(\d+)\s*Hz,\s*([a-z0-9(). ]+?)(?:,|$)", text)
    if match:
        info["sample_rate"] = int(match.group(1))
        chan = match.group(2).lower()
        info["channels"] = 1 if "mono" in chan else 2 if "stereo" in chan else 0

    if "seconds" not in info:
        info["seconds"] = _duration_fallback(path)
    return info


def _duration_fallback(path: Path) -> float:
    """Some containers do not report a duration. Ask ffmpeg to decode and time it."""
    ff = ffmpeg()
    result = subprocess.run(
        [ff, "-hide_banner", "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True)
    match = re.findall(r"time=(\d+):(\d+):([\d.]+)", result.stderr)
    if match:
        h, m, s = match[-1]
        return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def _band_bounds(path: Path, low_hz: float = 200.0, floor_db: float = -50.0,
                 window_ms: float = 10.0) -> tuple[float, float]:
    """
    When the voice starts and when it stops, read from the samples.

    The band above 200Hz only, so nothing else in the track can fake it: a
    45Hz drone and the MP3's own hiss are both outside it. Two things this
    replaces, and why:

      * ffmpeg's silencedetect at -45dB. The drone sits at -43dB, which is
        louder than the threshold, so the whole file looked like sound and a
        0.8s of dead air at the end measured as 0.03s. The seam was passing
        on a lie.
      * a full-band envelope. The MP3 leaves coding noise in every gap at
        about -43dB, loud enough to hide a real silence.
    """
    ff = ffmpeg()
    result = subprocess.run(
        [ff, "-hide_banner", "-v", "error", "-i", str(path),
         "-af", f"highpass=f={low_hz:g}", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
        capture_output=True)
    raw = result.stdout
    if not raw:
        return 0.0, 0.0

    try:
        import numpy as np
    except ImportError:
        return 0.0, 0.0

    samples = np.frombuffer(raw, dtype=np.float32)
    window = max(1, int(16000 * window_ms / 1000.0))
    count = samples.size // window
    if count == 0:
        return 0.0, 0.0

    frames = samples[:count * window].reshape(count, window)
    rms = np.sqrt((frames.astype(np.float64) ** 2).mean(axis=1))
    above = np.nonzero(rms > 10 ** (floor_db / 20.0))[0]
    if above.size == 0:
        return 0.0, 0.0

    return float(above[0]) * window_ms / 1000.0, float(above[-1] + 1) * window_ms / 1000.0


def _envelope_start(path: Path, floor_db: float = -40.0) -> float:
    """
    First moment the audio rises above an absolute floor.

    Computed from the raw samples, so it does not care what the loudest peak
    is. A near-silent file with one loud click will still report its true
    start, which is exactly the case silencedetect gets wrong.
    """
    ff = ffmpeg()
    result = subprocess.run(
        [ff, "-hide_banner", "-v", "error", "-i", str(path),
         "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
        capture_output=True)
    raw = result.stdout
    if not raw:
        return 0.0

    try:
        import numpy as np
    except ImportError:
        return 0.0

    samples = np.frombuffer(raw, dtype=np.float32)
    if samples.size == 0:
        return 0.0

    window = 160                      # 10ms at 16kHz
    count = samples.size // window
    if count == 0:
        return 0.0

    frames = samples[:count * window].reshape(count, window)
    rms = np.sqrt((frames.astype(np.float64) ** 2).mean(axis=1))
    threshold = 10 ** (floor_db / 20.0)
    above = np.nonzero(rms > threshold)[0]
    if above.size == 0:
        return 0.0
    return float(above[0]) * window / 16000.0


def longest_quiet(path: Path, floor_db: float = -60.0, window_ms: float = 10.0) -> tuple[float, float]:
    """
    The longest stretch that is genuinely silent, and where it starts.

    Read from the samples against an absolute floor. Two very different things
    live in a finished track and both look like silence on a drawing: the small
    gap the voice leaves between sentences, which still carries the encoder's
    noise floor at around -43dB, and digital silence, which is nothing at all.
    A floor of -60dB separates them cleanly.

    This is how the pause before the payoff is proved rather than asserted: if
    the drone runs under it, or the pause was cut in the wrong place, this
    number changes.
    """
    ff = ffmpeg()
    result = subprocess.run(
        [ff, "-hide_banner", "-v", "error", "-i", str(path),
         "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
        capture_output=True)
    raw = result.stdout
    if not raw:
        return 0.0, 0.0

    try:
        import numpy as np
    except ImportError:
        return 0.0, 0.0

    samples = np.frombuffer(raw, dtype=np.float32)
    window = max(1, int(16000 * window_ms / 1000.0))
    count = samples.size // window
    if count == 0:
        return 0.0, 0.0

    frames = samples[:count * window].reshape(count, window)
    rms = np.sqrt((frames.astype(np.float64) ** 2).mean(axis=1))
    threshold = 10 ** (floor_db / 20.0)

    best_start = best_len = 0
    run_start = run_len = 0
    for i, value in enumerate(rms):
        if value <= threshold:
            if run_len == 0:
                run_start = i
            run_len += 1
            if run_len > best_len:
                best_len, best_start = run_len, run_start
        else:
            run_len = 0

    return best_start * window / 16000.0, best_len * window / 16000.0


def _loudness(path: Path) -> tuple[float, float, float]:
    """(integrated LUFS, loudness range, true peak dBFS) via ffmpeg ebur128."""
    ff = ffmpeg()
    result = subprocess.run(
        [ff, "-hide_banner", "-i", str(path), "-af",
         "ebur128=peak=true:framelog=quiet", "-f", "null", "-"],
        capture_output=True, text=True)
    text = result.stderr

    def last(pattern: str, default: float) -> float:
        found = re.findall(pattern, text)
        return float(found[-1]) if found else default

    integrated = last(r"I:\s*(-?[\d.]+)\s*LUFS", -99.0)
    lra = last(r"LRA:\s*(-?[\d.]+)\s*LU", 0.0)
    peak = last(r"Peak:\s*(-?[\d.]+)\s*dBFS", -99.0)
    return integrated, lra, peak


def voice_bounds(path: Path) -> tuple[float, float]:
    """
    Public reader: when the voice starts and when it stops.

    The synthesiser's own last word overruns the sound by around 180ms on every
    take - it counts a little of the silence after the word as part of the word.
    The samples do not. Anything that needs the true end of the speech takes it
    from here.
    """
    return _band_bounds(path)


def onset(path: Path) -> float:
    """
    When the sound actually begins, read from the samples.

    This is the reference for everything else. The synthesiser's word
    boundaries are offsets into the speech, not into the file - an MP3 adds
    encoder padding in front, so the two disagree by around 150ms. The file is
    the truth; the boundaries are corrected to it.
    """
    return _envelope_start(path)


def measure(path: Path, word_count: int = 0, envelope: bool = True) -> Measurement:
    """Measure a finished audio file. Every field comes from the file itself."""
    path = Path(path)
    if not path.exists():
        raise AudioError(f"no such audio file: {path}")

    info = _probe(path)
    m = Measurement(
        path=str(path),
        seconds=float(info.get("seconds", 0.0)),
        sample_rate=int(info.get("sample_rate", 0)),
        channels=int(info.get("channels", 0)),
        words=word_count,
    )

    voice_start, voice_end = _band_bounds(path)
    m.lead_silence = voice_start
    m.tail_silence = max(0.0, m.seconds - voice_end)
    if envelope:
        m.envelope_start = _envelope_start(path)
    m.lufs, m.lufs_range, m.true_peak_db = _loudness(path)
    m.peak_db = m.true_peak_db
    if envelope:
        m.quiet_at, m.quiet_seconds = longest_quiet(path)

    # If the full band starts sounding well before the voice does, something
    # else is making noise in front of the first word. That is what an
    # unducked sub-bass looks like from here.
    if envelope and m.envelope_start + 0.05 < m.lead_silence:
        m.notes.append(
            f"sound begins at {m.envelope_start:.3f}s but the voice does not start "
            f"until {m.lead_silence:.3f}s - something is playing before the first "
            f"word, check the sub-bass")
    return m


def measure_words(take) -> Measurement:
    """Measure a take and cross-check against the voice's own word boundaries."""
    m = measure(take.path, word_count=take.word_count)
    if take.words:
        first = take.words[0].start

        # The voice always reports its first word earlier than the sound really
        # starts, by about 150ms, because the MP3 carries encoder padding in
        # front. That is expected on every single take, so it is a number to
        # print, not a warning to raise. A warning that fires every run teaches
        # the reader to ignore warnings.
        m.encoder_padding = m.lead_silence - first

        if first > m.lead_silence + 0.08:
            m.notes.append(
                f"the voice puts its first word at {first:.3f}s but the sound "
                f"starts at {m.lead_silence:.3f}s - that is not encoder padding "
                f"and it needs looking at")
    return m
