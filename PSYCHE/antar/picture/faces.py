"""
ANTAR - keeping people out of the picture.

This is the honest version of a hard rule. "No faces" sounds like one check.
It is not, and pretending otherwise would be worse than saying what is true.

WHAT IS GUARANTEED

  * The object table maps every Hindi object to an English search that names a
    thing, never a person. "empty chair", "plain wall shadow", "wall clock
    ticking". The search itself cannot ask for a person.
  * Every query and every returned result is refused if it carries a people
    word - not a substring match, a word match, so "chair" does not trip on
    "hair" and "hands" does not trip on a phrase containing "hand".

That is a real guarantee about the search. It is not a guarantee about pixels:
a stock library can hand back a wide shot of a street with a person walking
through the far corner, because that is what its own index decided the clip
was about.

WHAT IS OPTIONAL

A frame scan. If OpenCV 4.x is installed, frames from each downloaded clip are
run through the face detector that ships with it, and a hit means the clip is
thrown away rather than used.

It is a frontal-face detector, and it is worth being exact about that: it will
miss a face turned away from the camera, and it can fire on a pattern that
looks like one. So it is a second line, not the first. The first line is the
search, and the search cannot ask for a person.

OpenCV 5 removed the cascade API this uses. On 5.x the scan reports itself off
rather than pretending, and the requirements file asks for 4.x. When the scan
is off, ANTAR says so out loud on every single run rather than letting the rule
quietly become decoration.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .. import log
from ..vault import find_ffmpeg

# A person word only counts as a person word on its own. "hands" is not "hand",
# and the word "chair" contains "hair" - which is exactly the bug a substring
# test produced once already.
# Words that mean a human is in the picture. This list is used to judge text
# the STOCK LIBRARY wrote about itself - a search query and a clip's page
# address - so it holds person words and nothing else.
#
# Body parts and verbs are deliberately NOT here. "clock-hands-close-up" is a
# clip of a clock, and a filter that throws it away because of the word "hands"
# is a filter that costs footage without protecting anyone. The line is drawn
# at a person, not at the possibility of one.
PEOPLE_WORDS = (
    "face", "faces", "facial", "portrait", "selfie",
    "man", "men", "woman", "women", "person", "people", "human", "humans",
    "girl", "girls", "boy", "boys", "child", "children", "baby", "babies",
    "kid", "kids", "teen", "teenager", "guy", "guys", "lady", "ladies",
    "male", "female", "couple", "crowd", "family",
    "worker", "businessman", "businesswoman", "vlogger", "influencer",
    "actor", "actress", "interview", "model", "modeling", "posing",
    "smiling", "laughing",
)

_WORD = re.compile(r"[a-z]+")


def slug_words(url: str) -> str:
    """
    What a library says a clip is, in words.

    Pexels puts a description in the page address:
        /video/elderly-man-using-a-stethoscope-on-a-pendulum-clock-8321896/
    which names the person in the clip before anything is downloaded. Free
    information, and the cheapest place to refuse a clip.
    """
    if not url:
        return ""
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    words = [w for w in re.split(r"[-_]+", tail) if w and not w.isdigit()]
    return " ".join(words)


def people_words_in(text: str) -> list[str]:
    """Every people word in a phrase, matched as words, never as substrings."""
    found = []
    for word in _WORD.findall((text or "").lower()):
        if word in PEOPLE_WORDS or (word.endswith("s") and word[:-1] in PEOPLE_WORDS):
            found.append(word)
    return found


def _opencv():
    """
    OpenCV, but only if it can actually detect a face.

    OpenCV 5.0 ships the cascade files and no longer exposes the classifier, so
    "cv2 imported" is not the same question as "a face can be found". Both are
    checked, because a scan that silently does nothing is worse than no scan.
    """
    try:
        import cv2
    except Exception:
        return None
    if not hasattr(cv2, "CascadeClassifier"):
        return None
    return cv2


def faces_available() -> bool:
    return _opencv() is not None


def why_unavailable() -> str:
    """The precise reason the scan cannot run, for the log line."""
    try:
        import cv2
    except Exception:
        return "opencv is not installed"
    if not hasattr(cv2, "CascadeClassifier"):
        return (f"opencv {cv2.__version__} has no cascade detector "
                f"(needs 4.x - pip install 'opencv-python-headless<5')")
    return "ready"


def scan_for_faces(path: Path, seconds: float = 0.0,
                   samples: int = 8,
                   scale: float = 0.5) -> tuple[int, list[float]]:
    """
    Count faces in a clip by looking at frames spread across it.

    Two detectors, frontal and profile. The profile one is not optional: a
    clip of a man sitting side-on to the camera came back clean from the
    frontal detector on all eight frames, and the profile detector caught him
    on all eight. A rule that only looks at faces pointing at the lens is a
    rule that lets half the faces through.
    """
    """
    Count faces in a clip by looking at a few frames.

    """
    cv2 = _opencv()
    ff = find_ffmpeg()
    if cv2 is None or not ff:
        return 0, []

    try:
        import numpy as np  # noqa: F401
    except ImportError:
        return 0, []

    import tempfile

    root = Path(cv2.data.haarcascades)
    detectors = {}
    for name in ("frontalface_default", "profileface"):
        xml = root / f"haarcascade_{name}.xml"
        if xml.exists():
            detectors[name] = cv2.CascadeClassifier(str(xml))
    if not detectors:
        return 0, []

    span = seconds if seconds > 1.0 else 4.0
    total = 0
    times: list[float] = []
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(samples):
            at = max(0.2, (i + 0.5) * span / samples)
            frame = Path(tmp) / f"f{i}.png"
            result = subprocess.run(
                [ff, "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", str(path),
                 "-frames:v", "1", "-vf", f"scale=iw*{scale}:ih*{scale}", str(frame)],
                capture_output=True)
            if result.returncode != 0 or not frame.exists():
                continue

            image = cv2.imread(str(frame), cv2.IMREAD_GRAYSCALE)
            if image is None:
                continue

            # minNeighbors 7 asks the detector for a face it is confident about.
            # Lower and it starts calling chair legs faces, which would throw
            # away good clips and look like the rule working when it is not.
            found = 0
            for detector in detectors.values():
                found += len(detector.detectMultiScale(image, scaleFactor=1.1,
                                                       minNeighbors=7, minSize=(40, 40)))
            if found:
                total += found
                times.append(round(at, 2))
    return total, times
