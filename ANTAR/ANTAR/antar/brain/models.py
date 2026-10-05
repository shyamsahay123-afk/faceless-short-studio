"""
ANTAR - model ranking.

The rule this exists to enforce:

    The strongest model the key is entitled to must write every script.
    A weak model answering must never stop the engine reaching a strong one.

How it works: the live catalogue is fetched from the provider, then ranked by
a scoring function that reads what the model name actually says about size,
generation and tier. Nothing is hardcoded to a list that will be stale in a
month - a stale list is how the old engine ended up calling models that had
been shut down.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .. import log

# names that are never a writing model, whatever their score
EXCLUDE_PATTERNS = (
    "whisper", "tts", "embedding", "embed", "guard", "moderation",
    "vision-only", "audio", "image", "rerank", "classifier",
)

# size hints, biggest first
SIZE = (
    (r"(\d{3,4})b", 1.0),      # 120b, 405b
    (r"(\d{1,2})b", 0.6),      # 8b, 20b, 70b
)

TIER_UP = {"pro": 0.30, "ultra": 0.35, "max": 0.30, "premier": 0.25, "advanced": 0.25}
TIER_DOWN = {"mini": -0.20, "lite": -0.35, "small": -0.25, "tiny": -0.45,
             "nano": -0.40, "instant": -0.30, "flash-lite": -0.35}

# a newer generation wins
GENERATION = (
    (r"gemini-(\d+)(?:\.(\d+))?", 0.55),
    (r"gpt-oss", 0.30),
    (r"(\d)(?:\.(\d))?-flash", 0.20),
)


@dataclass
class Candidate:
    service: str
    model: str
    score: float
    why: str

    def __str__(self) -> str:
        return f"{self.service}/{self.model}  ({self.score:.2f}  {self.why})"


def _score(model: str) -> tuple[float, str]:
    name = model.lower()
    score = 0.0
    reasons: list[str] = []

    for pattern, weight in GENERATION:
        match = re.search(pattern, name)
        if match:
            groups = [g for g in match.groups() if g]
            if len(groups) >= 2:
                bump = weight * (1 + int(groups[0]) * 0.1 + int(groups[1]) * 0.02)
            elif groups and groups[0].isdigit():
                bump = weight * (1 + int(groups[0]) * 0.1)
            else:
                bump = weight
            score += bump
            reasons.append(f"+{bump:.2f} generation")
            break

    for pattern, weight in SIZE:
        match = re.search(pattern, name)
        if match:
            billions = int(match.group(1))
            # a log curve: 120b crushes 8b, but 405b is not 3x better than 120b
            import math
            bump = weight * math.log10(max(billions, 2) + 1)
            score += bump
            reasons.append(f"+{bump:.2f} size {billions}b")
            break

    for word, delta in TIER_UP.items():
        if word in name:
            score += delta
            reasons.append(f"+{delta:.2f} tier {word}")
            break
    else:
        for word, delta in TIER_DOWN.items():
            if word in name:
                score += delta
                reasons.append(f"{delta:.2f} tier {word}")
                break

    if "preview" in name or "experimental" in name or "exp" in name.split("-"):
        score -= 0.05
        reasons.append("-0.05 preview")

    if "deprecated" in name or "legacy" in name:
        score -= 1.0
        reasons.append("-1.00 deprecated")

    return score, ", ".join(reasons) or "no signals"


def is_writer(model: str) -> bool:
    name = model.lower()
    return not any(bad in name for bad in EXCLUDE_PATTERNS)


def rank(service: str, model_ids: list[str]) -> list[Candidate]:
    """Best writer first."""
    out: list[Candidate] = []
    for model in model_ids:
        if not is_writer(model):
            continue
        score, why = _score(model)
        out.append(Candidate(service, model, score, why))
    out.sort(key=lambda c: c.score, reverse=True)
    return out


def ladder(brain, prefer: list[str] | None = None) -> list[Candidate]:
    """
    The order models will be tried in: every service the user has keys for,
    in order of how generous their free tier is. The first service to give a
    usable answer wins; the rest are skipped.

    Order chosen so a single dead vendor doesn't stop the run:

      gemini        - 60 req/min free, rarely dies
      groq          - fast, but free keys die after ~1 hour of use
      openrouter    - free multi-model gateway, 50 req/day
      huggingface   - free, slow but durable
      together      - free credits
      openai        - paid; small free credit
      anthropic     - paid

    A dead key in one vendor does NOT block the other vendors.

    Fallback rule: when every FREE vendor has returned "all keys
    exhausted" (not "dead" - dead keys are a different signal, the
    vendor itself rejected the key), the ladder flips brain's
    force_resurrect flag so the next call into a PAID vendor can
    revive an exhausted key. This is the difference between "we
    spent our free credits, pay up" and "the keys are bad, give up".
    """
    FREE_SERVICES = ("gemini", "groq", "openrouter", "huggingface", "together")
    PAID_SERVICES = ("openai", "anthropic")
    ALL_SERVICES = FREE_SERVICES + PAID_SERVICES

    prefer = prefer or []
    candidates: list[Candidate] = []
    seen: set[str] = set()

    # First pass: check the keyring directly to see which free services
    # have keys on file. list_models() can't tell us - it returns [] on
    # both "no key on file" and "key is exhausted". We need to distinguish.
    free_vendors_with_keys: set[str] = set()
    free_vendors_drained: set[str] = set()
    try:
        ring = brain.ring
        for service in FREE_SERVICES:
            service_keys = [k for k in ring.all() if k.service == service]
            if not service_keys:
                continue
            free_vendors_with_keys.add(service)
            if all(k.state in ("dead", "exhausted") or k.value in getattr(ring, "_tried_this_run", set())
                   for k in service_keys):
                free_vendors_drained.add(service)
    except Exception:
        pass

    for service in ALL_SERVICES:
        ids = brain.list_models(service)
        if not ids:
            log.warn(f"{service}: no models visible - every key down or unreachable")

        ranked = rank(service, ids)
        by_name = {c.model: c for c in ranked}

        for wanted in prefer:
            for name, candidate in by_name.items():
                if wanted == name or wanted in name:
                    if name in seen:
                        continue
                    candidate.why = "preferred by config; " + candidate.why
                    candidates.append(candidate)
                    seen.add(name)
                    break

        for candidate in ranked:
            if candidate.model in seen:
                continue
            candidates.append(candidate)
            seen.add(candidate.model)

    # Decide whether to flip the Brain's force_resurrect flag.
    # The trigger: every free service that has keys on file is now drained
    # (keys are dead, exhausted, or already tried this run). When that
    # happens, the next call into a PAID service can resurrect an
    # exhausted paid key, so the run doesn't die when only paid options
    # remain.
    if free_vendors_with_keys and free_vendors_drained >= free_vendors_with_keys:
        if not getattr(brain, "_force_resurrect_on", False):
            log.warn("all free vendors drained - resurrecting exhausted paid keys for fallback")
            brain._force_resurrect_on = True

    return candidates


def should_force_resurrect(brain) -> bool:
    """Caller-side helper so provider methods don't need a back-pointer."""
    return bool(getattr(brain, "_force_resurrect_on", False))
