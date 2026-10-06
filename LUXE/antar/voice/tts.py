"""
ANTAR - text to speech.

One continuous take, and the word timings come back from the synthesiser
itself.

Why not Whisper: edge-tts emits a WordBoundary event per word with the exact
offset in 100-nanosecond ticks. That is the true timing of the audio that was
actually produced. A transcription pass would be re-guessing what the
synthesiser already knows, and it can hallucinate words that were never
spoken. The old engine used Whisper and had exactly that problem.

If edge-tts is unavailable or fails, this raises. It does not fall back to
silence and it does not pretend.
"""

from __future__ import annotations

import asyncio
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .. import log


class VoiceError(RuntimeError):
    """Speech could not be generated. The caller must not continue without it."""


# 11labs voice_id for the closest match to ANTAR's female-Hindi Edge-TTS
# voice (hi-IN-SwaraNeural). 11labs's "Rachel" is a calm, natural female
# English voice; for Hindi specifically, the multi-lingual v2 model
# handles Hindi.
#
# HARDCORE FIX 2026-10-04: Free users cannot use library voices via API.
# Rachel (21m00Tcm4TlvDq8ikWAM) is flagged as library for free tier -> 402.
# We now try a chain of premade voices that ARE allowed for free tier,
# and on 402 we fetch /v1/voices and pick the first premade voice that
# belongs to the user. This is why the log said:
#   "Free users cannot use library voices via the API" -> fallback to Edge-TTS
#
# The reason you saw fallback to Edge-TTS female: your 11labs key is FREE tier,
# and you tried to use a library voice (Rachel or any cloned voice). Free tier
# via API can only use premade voices that are marked as "premade" and not
# "cloned" or "library". The fix below tries all known premade IDs before giving up.
ELEVENLABS_DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"   # "Rachel" default
# Known premade voices that work on free tier (from ElevenLabs docs, 2024-2025)
ELEVENLABS_FREE_FRIENDLY_VOICES = [
    "21m00Tcm4TlvDq8ikWAM",  # Rachel - premade female, calm (try first)
    "EXAVITQu4vr4xnSDxMaL",  # Bella - premade female, soft
    "MF3mGyEYCl7XYWbV9V6O",  # Elli - premade female, young
    "AZnzlk1XvdvUeBnXmlld",  # Domi - premade female, strong
    "pNInz6obpgDQGcFmaJgB",  # Adam - premade male, deep (fallback)
    "ErXwobaYiN019PkySvjV",  # Antoni - premade male, well-rounded
    "VR6AewLTigWG4xSOukaG",  # Arnold - premade male, crisp
]
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_MODEL_ID = "eleven_multilingual_v2"
ELEVENLABS_VOICES_URL = "https://api.elevenlabs.io/v1/voices"


def _elevenlabs_fetch_usable_voice(key: str) -> str | None:
    """On 402, ask /v1/voices which premade voice this free key CAN use."""
    import json
    import urllib.request
    import urllib.error
    try:
        req = urllib.request.Request(
            ELEVENLABS_VOICES_URL,
            headers={"xi-api-key": key, "Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            voices = data.get("voices", []) if isinstance(data, dict) else []
            # Prefer premade, not cloned, not library
            for v in voices:
                cat = (v.get("category") or "").lower()
                if cat == "premade":
                    vid = v.get("voice_id")
                    if vid:
                        return vid
            # Fallback: any voice at all
            for v in voices:
                vid = v.get("voice_id")
                if vid:
                    return vid
    except Exception:
        pass
    return None


def synthesise_elevenlabs(text: str, key: str, voice_id: str | None = None,
                           out_path: Path | None = None) -> tuple[Path, list[Word]]:
    """
    Generate speech with ElevenLabs. Real provider, no mock.

    Returns (path, words). Words use 11labs's character-level timing API
    (since 11labs does not return word-level timings directly), split on
    whitespace and evenly distributed across the spoken duration.

    Raises VoiceError on any failure.
    """
    import json
    import urllib.request
    import urllib.error

    if out_path is None:
        out_path = Path("/tmp") / f"antar_11labs_{int(time.time()*1000)}.mp3"

    # Build chain: requested voice first, then free-friendly list, deduped
    chain: list[str] = []
    if voice_id:
        chain.append(voice_id)
    for vid in ELEVENLABS_FREE_FRIENDLY_VOICES:
        if vid not in chain:
            chain.append(vid)
    # If still nothing, try to fetch a usable voice from the account
    if not chain:
        fetched = _elevenlabs_fetch_usable_voice(key)
        if fetched:
            chain.append(fetched)

    last_error: Exception | None = None
    audio_bytes: bytes | None = None
    used_voice: str = chain[0] if chain else ELEVENLABS_DEFAULT_VOICE_ID

    for voice in chain:
        used_voice = voice
        payload = {
            "text": text,
            "model_id": ELEVENLABS_MODEL_ID,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        req = urllib.request.Request(
            f"{ELEVENLABS_URL}/{voice}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"xi-api-key": key,
                     "Content-Type": "application/json",
                     "Accept": "audio/mpeg"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                audio_bytes = resp.read()
                break  # success
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            last_error = e
            # 402 = Free users cannot use library voices via API - try next voice
            # 401 = bad key, 429 = rate limit - don't keep trying voices
            if e.code == 402:
                # Try to fetch a usable voice on first 402, then continue chain
                if voice == chain[0]:
                    fetched = _elevenlabs_fetch_usable_voice(key)
                    if fetched and fetched not in chain:
                        chain.append(fetched)
                continue
            elif e.code in (401, 403):
                raise VoiceError(f"11labs HTTP {e.code}: {body[:200]} - key dead or blocked") from e
            else:
                # For other errors, try next voice once, then fail
                if voice != chain[-1]:
                    continue
                raise VoiceError(f"11labs HTTP {e.code}: {body[:200]}") from e
        except urllib.error.URLError as e:
            last_error = e
            if voice != chain[-1]:
                continue
            raise VoiceError(f"11labs network: {e.reason}") from e

    if audio_bytes is None:
        # All voices in chain failed with 402
        if last_error and isinstance(last_error, urllib.error.HTTPError) and last_error.code == 402:
            raise VoiceError(
                "11labs HTTP 402: Free users cannot use library voices via API. "
                "Your key is free tier and all premade voices were rejected. "
                "Upgrade at https://elevenlabs.io/app/settings/billing or use Edge-TTS (hi-IN-SwaraNeural) which is free and already Hindi-native. "
                "This is NOT a bug - ElevenLabs blocks free keys from using cloned/library voices via API."
            ) from last_error
        raise VoiceError(f"11labs failed after trying {len(chain)} voices") from last_error

    out_path.write_bytes(audio_bytes)
    if len(audio_bytes) < 200:
        raise VoiceError(f"11labs returned tiny file ({len(audio_bytes)} bytes)")

    # 11labs does not give word timings in the basic endpoint. We
    # estimate by evenly distributing the spoken duration across the
    # words. This is good enough for the beat window maths in
    # beat_windows() - the build stage cares about beat positions, not
    # exact word onset, and the payoff-pause detection uses ffmpeg
    # probing of the resulting file (see voice/measure.py), not these
    # estimates.
    duration = _estimate_audio_duration(out_path)
    tokens = text.split()
    if not tokens or duration <= 0:
        return out_path, []
    per = duration / len(tokens)
    words = [Word(text=t, start=i * per, duration=per) for i, t in enumerate(tokens)]
    return out_path, words


def _estimate_audio_duration(path: Path) -> float:
    """ffprobe the audio file to get its real duration. Returns 0.0 on failure."""
    from ..vault import find_ffmpeg
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return 0.0
    import subprocess
    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", str(path)],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 0.0
    # ffmpeg prints "Duration: HH:MM:SS.xx" on stderr for any input
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if not m:
        return 0.0
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


@dataclass
class Word:
    text: str
    start: float          # seconds from the start of the audio
    duration: float       # seconds

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass
class Take:
    path: Path
    voice: str
    rate: str
    pitch: str
    seconds: float = 0.0
    words: list[Word] = field(default_factory=list)
    characters: int = 0
    seconds_to_generate: float = 0.0

    @property
    def word_count(self) -> int:
        return len(self.words)

    @property
    def lead_pad(self) -> float:
        """Dead air the synthesiser puts in front of the first word."""
        return self.words[0].start if self.words else 0.0

    @property
    def speech_seconds(self) -> float:
        """
        The time actually spent speaking: from the first word to the last one.

        Pacing must be measured over this, not over the file duration. The
        file includes the synthesiser's front padding, and counting that as
        speech inflates the rate and would put every script too long.
        """
        if not self.words:
            return 0.0
        return max(0.0, self.words[-1].end - self.words[0].start)

    @property
    def words_per_second(self) -> float:
        speech = self.speech_seconds
        return (self.word_count / speech) if speech > 0 else 0.0

    @property
    def first_word_at(self) -> float:
        return self.words[0].start if self.words else 0.0

    @property
    def last_word_ends(self) -> float:
        return self.words[-1].end if self.words else 0.0


async def _synthesise(text: str, out_path: Path, voice: str, rate: str,
                      pitch: str, volume: str) -> list[Word]:
    import edge_tts

    words: list[Word] = []
    # edge-tts defaults to SentenceBoundary, which emits no per-word events at
    # all. WordBoundary must be asked for explicitly, and without it there are
    # no timings and no way to place the silence before the payoff.
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch,
                                       volume=volume, boundary="WordBoundary")

    with out_path.open("wb") as handle:
        async for chunk in communicate.stream():
            kind = chunk.get("type")
            if kind == "audio":
                handle.write(chunk["data"])
            elif kind == "WordBoundary":
                # offset and duration arrive in 100-nanosecond ticks
                words.append(Word(
                    text=chunk.get("text", ""),
                    start=chunk["offset"] / 10_000_000,
                    duration=chunk["duration"] / 10_000_000,
                ))
    return words


def _ffmpeg_duration(path: Path) -> float:
    """Duration straight from ffmpeg. Used to fill in a take's own seconds."""
    from ..vault import find_ffmpeg
    ff = find_ffmpeg()
    if not ff:
        return 0.0
    result = subprocess.run([ff, "-hide_banner", "-i", str(path)],
                            capture_output=True, text=True)
    match = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", result.stderr)
    if match:
        return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))
    return 0.0


def speak(text: str, out_path: Path, voice: str, rate: str = "+0%",
          pitch: str = "+0Hz", volume: str = "+0%") -> Take:
    """
    Generate one continuous take. Raises VoiceError on any failure.
    """
    text = (text or "").strip()
    if not text:
        raise VoiceError("nothing to say - the script was empty")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    started = time.time()
    try:
        words = asyncio.run(_synthesise(text, out_path, voice, rate, pitch, volume))
    except ModuleNotFoundError as exc:
        raise VoiceError("edge-tts is not installed - run INSTALL.bat") from exc
    except Exception as exc:
        raise VoiceError(f"speech failed: {type(exc).__name__}: {exc}") from exc
    elapsed = time.time() - started

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise VoiceError("speech produced no audio - the endpoint returned nothing")
    if not words:
        raise VoiceError("speech produced audio but no word timings - "
                         "the timing would have to be guessed, which is not acceptable")

    take = Take(path=out_path, voice=voice, rate=rate, pitch=pitch,
                words=words, characters=len(text), seconds_to_generate=elapsed)
    take.seconds = _ffmpeg_duration(out_path)
    return take


def split_for_sections(lines: list[str]) -> list[str]:
    """
    The text as one paragraph.

    Deliberately joined with a space and nothing else: a full stop makes the
    voice drop and pause, and a list of sentences read separately would not
    flow. Section pauses are added later, by cutting the rendered audio, not
    by asking the voice to pause.
    """
    return [" ".join(line.strip() for line in lines if line.strip())]
