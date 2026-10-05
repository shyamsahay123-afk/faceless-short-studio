"""
ANTAR - picking one clip out of fifteen.

Chosen by rules, not by taste, and the same way every time. A video that
reshuffles itself between two runs of the same command is a video nobody can
work on.

Order of preference, and every step of it is printed:

  1. Nothing already used in THIS video. A repeat inside one video is not
     rotation, it is a rerun.
  2. Nothing the vault counts as a repeat, including lookalikes. That one is
     checked on the bytes once the clip is down, because a lookalike is not
     something a listing can tell you - it is what the picture looks like.
  3. Portrait, tall enough to fill the canvas, long enough to be cut into.
  4. No people words anywhere in the query or the offered result.
  5. The shortest clip that satisfies the rest, so the download and the vault
     stay small. More seconds than the beat needs is waste, not quality.
"""

from __future__ import annotations

import hashlib

from .faces import people_words_in
from .sources import Candidate


def _score(candidate: Candidate, target_seconds: float, min_seconds: float,
           prefer_height: int) -> tuple:
    """
    Lower is better. Deterministic, so equal clips still order the same.
    
    PREMIUM UPGRADE 2026-10-04:
    - Old: picked shortest clip that satisfies constraints - cheap look
    - New: prefer 1080x1920 exactly, longer duration, higher res, premium feel
    - Penalize clips that are too short or too tall (upscaled)
    """
    # Premium: exact 1080x1920 is best, not just any >=1920
    exact_match = 0 if (candidate.width == 1080 and candidate.height == 1920) else 1
    # Prefer clips closer to target but slightly longer (more to cut from)
    duration_score = abs(candidate.duration - target_seconds)
    if candidate.duration < target_seconds:
        duration_score += 2.0  # penalize short clips
    # Height score: prefer 1920, then higher, but not way too high (upscaled)
    height_score = 0 if candidate.height >= prefer_height else 1
    if candidate.height > 2200:
        height_score += 1  # likely upscaled, soft
    # Premium: larger files often = higher bitrate = better quality
    # But we invert so smaller file_url still deterministic tie-breaker
    return (
        0 if candidate.duration >= min_seconds else 1,
        duration_score,
        exact_match,
        height_score,
        -candidate.height,
        -candidate.megapixels,  # prefer higher megapixels
        candidate.file_url,
    )


def pick(candidates: list[Candidate], *, used_keys: set[str] | None = None,
         target_seconds: float = 4.0, min_seconds: float = 3.0,
         prefer_height: int = 1920, seed: str = "") -> tuple[Candidate | None, list[str]]:
    """
    The one clip worth downloading, and a note for every candidate refused.

    Returns (chosen or None, notes). None is a normal answer, not a failure:
    the beat then gets a text card.
    """
    used_keys = used_keys or set()
    notes: list[str] = []
    viable: list[Candidate] = []

    for candidate in candidates:
        if candidate.key in used_keys:
            notes.append(f"{candidate.key} already used in this video")
            continue
        if not candidate.portrait:
            notes.append(f"{candidate.key} is landscape")
            continue
        if candidate.duration and candidate.duration < min_seconds:
            notes.append(f"{candidate.key} is only {candidate.duration:.0f}s")
            continue

        offenders = people_words_in(candidate.query)
        if offenders:
            notes.append(f"{candidate.key} query names a person: {offenders}")
            continue

        # The library describes its own clips in the page address. Reading it
        # costs nothing and refuses a clip with a person in it BEFORE the
        # download, which is the cheapest place to refuse one.
        described = people_words_in(candidate.description)
        if described:
            notes.append(f"{candidate.key} is about a person: {described} "
                         f"({candidate.description[:38]})")
            continue

        viable.append(candidate)

    if not viable:
        return None, notes

    # A stable shuffle, so the same run always lands on the same clip, but two
    # different videos do not both start with whatever the library ranked first.
    def stable(candidate: Candidate) -> tuple:
        digest = hashlib.blake2b(f"{seed}|{candidate.key}".encode(),
                                 digest_size=8).hexdigest()
        return (int(digest, 16) & 0xFF, _score(candidate, target_seconds,
                                               min_seconds, prefer_height))

    viable.sort(key=stable)
    chosen = viable[0]
    return chosen, notes
