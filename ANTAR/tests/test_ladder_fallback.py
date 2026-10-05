"""
Tests for the ladder's force_resurrect logic.
The rule: when every free vendor is drained (all keys are dead, exhausted,
or already tried), the next call into a paid vendor can resurrect an
exhausted key so the run doesn't die when only paid options remain.

These tests use a fake Brain that doesn't hit the network.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

# Make antar importable from the test dir
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from antar.keys import KeyRing
from antar.brain.providers import Brain
from antar.brain import models


def _ring_with(keys):
    """Build a temp keyring from a list of dicts."""
    tmpdir = Path(tempfile.mkdtemp())
    path = tmpdir / "keys.json"
    payload = {"version": 1, "saved": time.time(), "count": len(keys), "keys": keys}
    path.write_text(json.dumps(payload))
    return KeyRing(path)


def _fake_brain(ring, model_map):
    """A Brain that returns the given model list for each service, no network."""

    class _Fake(Brain):
        def list_models(self, service):
            return list(model_map.get(service, []))

    return _Fake(ring)


def test_ladder_flips_force_resurrect_when_all_free_drained():
    # gemini + groq EXHAUSTED (drained), openai ALIVE
    ring = _ring_with([
        {"value": "gem-key-1", "service": "gemini", "state": "exhausted",
         "reason": "429", "added": time.time(), "uses": 1, "fails": 0},
        {"value": "grq-key-1", "service": "groq", "state": "exhausted",
         "reason": "429", "added": time.time(), "uses": 1, "fails": 0},
        {"value": "oai-key-1", "service": "openai", "state": "alive",
         "reason": "", "added": time.time(), "uses": 0, "fails": 0},
    ])
    brain = _fake_brain(ring, {
        "gemini": ["gemini-2.5-flash"],
        "groq": ["llama-3.3-70b"],
        "openai": ["gpt-4o-mini"],
    })
    assert not getattr(brain, "_force_resurrect_on", False), \
        "flag should start unset"
    models.ladder(brain)
    assert getattr(brain, "_force_resurrect_on", False), \
        "flag should be flipped after all free vendors drain"


def test_ladder_does_not_flip_when_a_free_vendor_is_alive():
    # gemini EXHAUSTED, groq ALIVE - flag should stay unset
    ring = _ring_with([
        {"value": "gem-key-1", "service": "gemini", "state": "exhausted",
         "reason": "429", "added": time.time(), "uses": 1, "fails": 0},
        {"value": "grq-key-1", "service": "groq", "state": "alive",
         "reason": "", "added": time.time(), "uses": 0, "fails": 0},
        {"value": "oai-key-1", "service": "openai", "state": "exhausted",
         "reason": "429", "added": time.time(), "uses": 1, "fails": 0},
    ])
    brain = _fake_brain(ring, {
        "groq": ["llama-3.3-70b"],
        "openai": ["gpt-4o-mini"],
    })
    models.ladder(brain)
    assert not getattr(brain, "_force_resurrect_on", False), \
        "flag should stay unset when a free vendor is alive"


def test_force_resurrect_returns_exhausted_paid_key():
    ring = _ring_with([
        {"value": "oai-key-1", "service": "openai", "state": "exhausted",
         "reason": "429", "added": time.time(), "uses": 1, "fails": 0},
    ])
    brain = _fake_brain(ring, {"openai": ["gpt-4o-mini"]})
    brain._force_resurrect_on = True
    k = brain._next_key_with_fallback("openai")
    assert k.value == "oai-key-1", f"got {k.masked}"


def test_force_resurrect_does_not_return_dead_key():
    ring = _ring_with([
        {"value": "oai-key-1", "service": "openai", "state": "dead",
         "reason": "401", "added": time.time(), "uses": 0, "fails": 1},
    ])
    brain = _fake_brain(ring, {"openai": ["gpt-4o-mini"]})
    brain._force_resurrect_on = True
    try:
        brain._next_key_with_fallback("openai")
        raise AssertionError("DEAD key was returned - this is a violation")
    except Exception:
        pass    # AllKeysDown is the expected result


def test_no_force_resurrect_blocks_exhausted_paid_key():
    """Without the flag, an exhausted paid key stays exhausted (the OLD bug)."""
    ring = _ring_with([
        {"value": "oai-key-1", "service": "openai", "state": "exhausted",
         "reason": "429", "added": time.time(), "uses": 1, "fails": 0},
    ])
    brain = _fake_brain(ring, {"openai": ["gpt-4o-mini"]})
    try:
        brain._next_key_with_fallback("openai")
        raise AssertionError("expected AllKeysDown without resurrect flag")
    except Exception:
        pass


if __name__ == "__main__":
    test_ladder_flips_force_resurrect_when_all_free_drained()
    print("PASS  ladder flips force_resurrect when all free vendors drain")
    test_ladder_does_not_flip_when_a_free_vendor_is_alive()
    print("PASS  ladder does not flip when a free vendor is alive")
    test_force_resurrect_returns_exhausted_paid_key()
    print("PASS  force_resurrect returns exhausted paid key")
    test_force_resurrect_does_not_return_dead_key()
    print("PASS  force_resurrect does not return DEAD key")
    test_no_force_resurrect_blocks_exhausted_paid_key()
    print("PASS  no force_resurrect blocks exhausted paid key")
    print("\nAll 5 tests passed")
