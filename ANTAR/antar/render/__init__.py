"""
ANTAR - the render.

This folder used to be called `build`, and that name cost a whole module: the
workspace snapshot drops any directory called `build`, so between two sessions
the render code disappeared and `run.py build` failed on the next command that
needed it. It is called `render` now. The command is still `python run.py
build` - only the folder inside the package changed.

Nothing else changed: the finished video is still made here.
"""

from .grade import (Grade, GradeError, NIGHT_TARGET, concat_and_mux,
                    encode_card, encode_clip, measure, probe_video,
                    scan_frames, solve)
from .render import (BuildError, BuiltShot, build, contact_sheet, latest_plan,
                     load_plan, verify)
from .typekit import (BuildError as TypeError_, Chunk, Popup, chunk_words,
                      load_font, place, render_popup)

__all__ = [
    "build", "load_plan", "latest_plan", "verify", "contact_sheet",
    "BuildError", "BuiltShot",
    "solve", "measure", "probe_video", "scan_frames", "concat_and_mux",
    "encode_clip", "encode_card", "Grade", "GradeError", "NIGHT_TARGET",
    "chunk_words", "render_popup", "place", "load_font", "Popup", "Chunk",
]
