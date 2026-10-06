"""
ANTAR - proof.

Phase 9: the test render, the real thumbnails, and the scorecard the
operator reads.

`prove()` runs the ten proofs from the master plan's test plan (section 11),
writes the chosen frame and the landscape thumbnail, and returns a single
record the panel and the report both read.

Two promises this file has to keep:

  * every proof is a number in the file, never a sentence that says "it
    works" - the proof file is the evidence, not a summary of it;
  * the scorecard this stage reads is the scorecard the upload reads - if
    the proof stage and the check stage ever disagree, the proof stage is
    wrong, not the upload gate.
"""

from .thumbnail import ThumbError, make_real_thumbnail, fallback_landscape, LANDSCAPE
from .evidence import ProofError, prove

__all__ = ["ThumbError", "make_real_thumbnail", "fallback_landscape",
           "LANDSCAPE", "ProofError", "prove"]
