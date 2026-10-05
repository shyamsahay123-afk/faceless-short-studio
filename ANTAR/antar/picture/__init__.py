"""
ANTAR - finding the picture for a line.

One beat names one object. That object becomes an English search, the stock
library is asked for portrait footage, one clip is chosen, and if nothing
usable comes back the beat gets a text card instead. That is the whole stage.

The rules that shape the choosing, all of them from the spec:

  * PORTRAIT ONLY. The canvas is 1080x1920 full bleed. A landscape clip has to
    be cropped to a third of itself to fit, and it looks it.
  * NO PEOPLE. Enforced at the search: the object table never names a person,
    and any query or result carrying a people word is refused before download.
    An optional frame scan catches the rest if OpenCV is installed - see
    faces.py, which is honest about what it can and cannot see.
  * A CLIP IS USED TWICE AT MOST, ever. The vault counts.
  * LOOKALIKES COUNT AS REPEATS. Two near-identical clips are one clip.
  * NO CLIP TWICE IN THE SAME VIDEO. That is not a reuse, that is a rerun.
  * THE CHOICE IS DETERMINISTIC. The same script and the same seed give the
    same plan, so a re-run does not reshuffle the video underneath you.
"""

from __future__ import annotations

from .sources import Candidate, SourceError, search, download, SERVICES
from .faces import scan_for_faces, faces_available
from .choose import pick, people_words_in
from .card import build_card, card_brightness
from .plan import build_plan, load_voice, save_plan, PictureError

__all__ = [
    "Candidate", "SourceError", "search", "download", "SERVICES",
    "scan_for_faces", "faces_available",
    "pick", "people_words_in",
    "build_card", "card_brightness",
    "build_plan", "save_plan", "load_voice", "PictureError",
]
