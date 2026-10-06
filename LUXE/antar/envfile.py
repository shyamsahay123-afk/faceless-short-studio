"""
ANTAR - the .env loader.

You paste an env file into the project folder. That is the entire setup
procedure. No import command, no panel, no typing keys in twice.

Where it looks, in order:
    1. ANTAR_ENV          a path you set, if you want it elsewhere
    2. <project>/.env     the normal place
    3. <project>/config/.env

Rules it keeps:
    * a key already on file is never added twice
    * a key marked dead stays dead, even if it reappears in the file
    * nothing is ever deleted
    * the value is read; the file is never moved, copied or modified

Reading a text file is not importing an old build. The keys are yours and
belong to no version of anything.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import log
from .keys import KeyRing

# How a variable name maps to a service. Order matters: the first hint that
# matches wins, so YOUTUBE is tested before GOOGLE (a YouTube data key is not
# a Gemini key), and GEMINI before GOOGLE for the same reason.
SERVICE_HINTS = (
    ("PEXELS", "pexels"),
    ("PIXABAY", "pixabay"),
    ("GROQ", "groq"),
    ("DEEPGRAM", "deepgram"),
    ("OPENAI", "openai"),
    ("ANTHROPIC", "anthropic"),
    ("CLAUDE", "anthropic"),
    ("ELEVENLABS", "elevenlabs"),
    ("HUGGINGFACE", "huggingface"),
    ("HUGGING", "huggingface"),
    ("HF_", "huggingface"),
    ("OPENROUTER", "openrouter"),
    ("TOGETHER", "together"),
    ("REPLICATE", "replicate"),
    ("STABILITY", "stability"),
    ("REMOVE_BG", "removebg"),
    ("REMOVEBG", "removebg"),
    ("SERPAPI", "serpapi"),
    ("SERP_API", "serpapi"),
    ("YOUTUBE", "youtube"),
    ("YT_", "youtube"),
    ("GEMINI", "gemini"),
    ("GOOGLE", "gemini"),
)

# Names that are clearly a key but not a service ANTAR can test yet. They are
# filed and kept, never thrown away, and the run says which services do have a
# check written - so nothing on file ever looks unidentified.
UNUSED_HINTS = ("MAPBOX", "TRANSLATE", "SPEECH", "FIREBASE", "STRIPE",
                "SENDGRID", "TWILIO")

PLACEHOLDERS = {"", "your_key_here", "changeme", "none", "null", "todo", "xxx"}


def candidate_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    override = os.environ.get("ANTAR_ENV")
    if override:
        paths.append(Path(override).expanduser())
    paths.append(root / ".env")
    paths.append(root / "config" / ".env")
    return paths


def _detect_service_from_value(value: str) -> str | None:
    """
    Best-effort detection of the service from the value alone, when the
    env-var name gives no hint. Each detection is conservative - false
    positives are worse than no detection, because a wrong service
    means the key goes to the wrong live-test endpoint and gets a
    spurious 401/403.

    The prefixes are vendor-published:
      gsk_           Groq
      sk-ant-        Anthropic
      sk-proj-       OpenAI project-scoped
      sk-svcacct-    OpenAI service account
      sk-            OpenAI (older)
      hf_            Huggingface
      xai-           xAI / Grok
      pplx-          Perplexity
      AIza           Google (Gemini or AI Studio)

    Pexels / Pixabay don't have a documented prefix; their keys are
    50+ chars of mixed-case alphanumerics. We don't try to detect
    them from value - they must come through a named env var.
    """
    if not value:
        return None
    # Groq
    if value.startswith("gsk_"):
        return "groq"
    # Anthropic (must check before generic sk-)
    if value.startswith("sk-ant-"):
        return "anthropic"
    # OpenAI - newer project keys and service-account keys
    if value.startswith("sk-proj-") or value.startswith("sk-svcacct-"):
        return "openai"
    # OpenAI - older and current standard keys
    if value.startswith("sk-"):
        return "openai"
    # Huggingface
    if value.startswith("hf_"):
        return "huggingface"
    # xAI / Grok
    if value.startswith("xai-"):
        return "groq"            # treat as groq-tier LLM (xai has no ladder slot yet)
    # Perplexity - real, but no provider wired yet
    if value.startswith("pplx-"):
        return None              # return None, log as unknown
    # Google AI Studio / Gemini
    if value.startswith("AIza"):
        return "gemini"
    return None


def parse(text: str) -> tuple[list[tuple[str, str]], list[str], list[str]]:
    """
    Read KEY=value lines.

    Returns (keys, unused_names, unreadable_names).
    A key is (service, value). Order is preserved, so KEY_1 comes before KEY_2.

    Service resolution order:
      1. SERVICE_HINTS from the env-var name (the existing path)
      2. _detect_service_from_value() from the value's prefix
      3. UNUSED_HINTS → filed in 'unused' but never deleted
      4. anything else → filed in 'unknown' with a clear note
    """
    keys: list[tuple[str, str]] = []
    unused: list[str] = []
    unknown: list[str] = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip().strip('"').strip("'")

        if value.lower() in PLACEHOLDERS:
            continue

        upper = name.upper()

        service = next((svc for hint, svc in SERVICE_HINTS if hint in upper), None)
        if service is None:
            # No hint from the name - try the value's prefix.
            service = _detect_service_from_value(value)

        if service is None:
            if any(hint in upper for hint in UNUSED_HINTS):
                unused.append(name)
            else:
                unknown.append(name)
            continue

        keys.append((service, value))

    return keys, unused, unknown


def load(root: Path, ring: KeyRing, quiet: bool = False) -> dict:
    """
    Read every candidate file and file the keys. Returns a summary dict.

    Safe to call on every start: it is idempotent and cheap.
    """
    summary = {"files": [], "added": 0, "already_on_file": 0, "unused": [],
               "unknown": [], "revived": []}

    for path in candidate_paths(root):
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            log.warn(f"env: could not read {path}: {exc}")
            continue

        keys, unused, unknown = parse(text)
        if not keys:
            continue

        added_here = 0
        for service, value in keys:
            existing = ring.find(value)
            if existing is not None:
                summary["already_on_file"] += 1
                # a dead key that reappears is still dead. history is kept.
                if existing.state == "dead":
                    summary["revived"].append(existing.masked)
                continue
            if len(ring) >= ring.max_keys:
                log.warn(f"env: key limit of {ring.max_keys} reached, {path.name} partly read")
                break
            try:
                ring.add(service, value)
                added_here += 1
            except ValueError:
                pass

        if added_here:
            summary["added"] += added_here
            summary["files"].append(f"{path.name} (+{added_here})")
        else:
            summary["files"].append(f"{path.name} (nothing new)")

        summary["unused"].extend(unused)
        summary["unknown"].extend(unknown)

    if not quiet:
        if summary["added"]:
            log.ok(f"env: filed {summary['added']} key(s) from {', '.join(summary['files'])}")
        elif summary["already_on_file"]:
            log.ok(f"env: {summary['already_on_file']} key(s) already on file - nothing to do")
        if summary["unused"]:
            log.info(f"env: recognised but unused by ANTAR: {', '.join(sorted(set(summary['unused'])))}")
        if summary["unknown"]:
            log.info(f"env: not filed (unknown service): {', '.join(sorted(set(summary['unknown'])))}")
        if summary["revived"]:
            log.warn(f"env: {len(summary['revived'])} key(s) reappeared in the file but are "
                     f"marked dead - they stay dead until you test them again")

    return summary
