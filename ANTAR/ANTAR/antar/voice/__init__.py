"""
ANTAR - the voice.

Four jobs, in order:

  1. TURN THE SCRIPT INTO ONE CONTINUOUS TAKE
     A single edge-tts call. Never line by line - stitching lines produces
     audible seams at every join.

  2. TAKE THE WORD TIMINGS FROM THE VOICE ITSELF
     Edge-TTS reports a WordBoundary event for every word with its exact
     offset. That is the real timing, given away for free. No transcription
     model is involved, so nothing can be misheard and no word can be
     invented.

  3. BUILD THE TRACK
     0.85s of dead silence before the payoff, cut to near-silence.
     45Hz sub-bass under the whole thing, synthesised here - no audio files.
     50ms fade at the tail so the loop point is inaudible.

  4. PROVE IT
     Duration, lead silence, tail silence, loudness. Numbers, not assurances.
"""

from . import build, measure, tts  # noqa: F401

__all__ = ["build", "measure", "tts"]
