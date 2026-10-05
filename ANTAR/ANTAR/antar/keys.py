"""
ANTAR - key health.

Four standing rules, each one paid for:

  1. A key that the API itself rejects is DEAD. It is never tried again.
     (key bleed) Only the API's own words count: a 403 from a firewall is
     BLOCKED, not dead, and the key stays usable.
  2. A key that hits a rate limit is EXHAUSTED for this run, not dead.
     The engine advances to the next key, and if every key is exhausted it
     advances the MODEL. A 429 is never grounds for another attempt on the
     same key.
  3. A dead or exhausted key is never deleted from the file. History matters.
  4. Nothing is classified by the shape of the string. A Gemini key is not
     recognised by a prefix; only a live call proves anything.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import log

ALIVE = "alive"
DEAD = "dead"              # the API said the key is wrong - never try again
EXHAUSTED = "exhausted"    # rate limited or quota spent
BLOCKED = "blocked"        # the site refused the request, the key is fine
UNKNOWN = "unknown"        # added but never tested

TERMINAL = {DEAD}


class AllKeysDown(RuntimeError):
    """Every key for this service is dead or exhausted."""


@dataclass
class Key:
    value: str
    service: str
    state: str = UNKNOWN
    reason: str = ""
    added: float = field(default_factory=time.time)
    last_checked: float = 0.0
    uses: int = 0
    fails: int = 0

    @property
    def masked(self) -> str:
        v = self.value
        if len(v) <= 10:
            return "***"
        return f"{v[:6]}...{v[-4:]}"


class KeyRing:
    """
    The key file. Never deletes. Never retries a failed key.

    On disk:
        {"keys": [ {value, service, state, reason, added, last_checked, uses, fails}, ... ],
         "version": 1}
    """

    def __init__(self, path: Path, max_keys: int = 50, never_delete: bool = True):
        self.path = Path(path)
        self.max_keys = max_keys
        self.never_delete = never_delete
        self._keys: list[Key] = []
        self._tried_this_run: set[str] = set()
        self.load()

    # -- persistence

    def load(self) -> None:
        if not self.path.exists():
            self._keys = []
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            log.warn(f"key file unreadable, starting empty: {exc}")
            self._keys = []
            return
        self._keys = []
        for payload in raw.get("keys", []):
            try:
                self._keys.append(Key(**payload))
            except TypeError:
                log.warn("a key entry was ignored (unexpected fields)")

    def save(self) -> None:
        from .vault import atomic_write_json
        atomic_write_json(self.path, {
            "version": 1,
            "saved": time.time(),
            "count": len(self._keys),
            "keys": [asdict(k) for k in self._keys],
        })

    # -- queries

    def __len__(self) -> int:
        return len(self._keys)

    def all(self) -> list[Key]:
        return list(self._keys)

    def for_service(self, service: str) -> list[Key]:
        return [k for k in self._keys if k.service == service]

    def health(self) -> dict:
        out: dict[str, dict[str, int]] = {}
        for key in self._keys:
            bucket = out.setdefault(key.service, {ALIVE: 0, DEAD: 0, EXHAUSTED: 0, UNKNOWN: 0})
            bucket[key.state] = bucket.get(key.state, 0) + 1
        return out

    def find(self, value: str) -> Key | None:
        for key in self._keys:
            if key.value == value:
                return key
        return None

    # -- the rotation

    def next_key(self, service: str, *, force_resurrect: bool = False) -> Key:
        """
        The next usable key for this service.

        Skips: anything dead, anything exhausted (unless force_resurrect),
        anything already tried in this run. Raises AllKeysDown rather than
        retrying a failure.

        force_resurrect is the ladder's escape hatch: when every free
        vendor has failed and the only path left is a paid one, the
        Brain calls next_key with force_resurrect=True. The exhausted
        key is allowed back in, but only one key per service, and only
        once per run.
        """
        for key in self._keys:
            if key.service != service:
                continue
            if key.state == DEAD:
                continue
            if key.state == EXHAUSTED and not force_resurrect:
                continue
            if key.value in self._tried_this_run:
                continue
            self._tried_this_run.add(key.value)
            return key
        raise AllKeysDown(
            f"no usable {service} key left this run "
            f"({len(self.for_service(service))} on file, all dead/exhausted/tried)"
        )

    def reset_run(self) -> None:
        """New run: exhausted keys become eligible again, dead ones do not."""
        self._tried_this_run.clear()
        for key in self._keys:
            if key.state == EXHAUSTED:
                key.state = ALIVE
                key.reason = "reset for new run"
        self.save()

    # -- results

    def revive(self, service: str = "") -> int:
        """
        Put dead keys back to unknown so they get tested again.

        Deliberate, never automatic. A key is only ever written off by a live
        reply, so the only honest way back is a fresh live reply - which is why
        this returns them to UNKNOWN rather than ALIVE. It exists because a
        check with a bug in it once marked four working keys dead, and the
        standing rule "never retry a failed key" would have made that permanent.
        """
        count = 0
        for key in self.all():
            if key.state == DEAD and (not service or key.service == service):
                key.state = UNKNOWN
                key.reason = "revived for a re-check"
                count += 1
        if count:
            self.save()
        return count

    def restore_quarantined(self, service: str = "") -> int:
        """
        Re-pull quarantined keys from keys_dead.json so they can be retested.

        Same effect as revive(), but the keys were not just marked dead, they
        were also moved out of the active ring. Use this when you really mean
        "ask every key on disk, no matter what".
        """
        dead_path = self.path.parent / "keys_dead.json"
        if not dead_path.exists():
            return 0
        try:
            raw = json.loads(dead_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return 0
        archive = raw.get("keys", []) if isinstance(raw, dict) else raw
        seen = {k.value for k in self._keys}
        restored = 0
        for payload in archive:
            if service and payload.get("service") != service:
                continue
            value = payload.get("value")
            if not value or value in seen:
                continue
            try:
                key = Key(value=value,
                           service=payload.get("service", ""),
                           reason="restored from quarantine for re-check",
                           state=UNKNOWN,
                           added=payload.get("added", 0),
                           last_checked=payload.get("died_at", 0),
                           uses=payload.get("uses", 0),
                           fails=payload.get("fails", 0))
                self._keys.append(key)
                seen.add(value)
                restored += 1
            except (TypeError, ValueError):
                continue
        if restored:
            self.save()
        return restored

    def mark_dead(self, value: str, reason: str = "401") -> None:
        key = self.find(value)
        if key is None:
            return
        key.state = DEAD
        key.reason = reason
        key.fails += 1
        key.last_checked = time.time()
        # quarantine: write the dead key to keys_dead.json before removing
        # from the active ring. The dead key stays on disk for inspection
        # but is never tried again - the active ring only has alive keys.
        self._quarantine(key)
        self._keys = [k for k in self._keys if k.value != value]
        self.save()
        log.warn(f"{key.service} key {key.masked} marked DEAD ({reason}) - "
                 f"moved to keys_dead.json, will not be tried again")

    def _quarantine(self, key: Key) -> None:
        """Append a dead key to keys_dead.json. Never overwrites, never deletes."""
        from .vault import atomic_write_json
        dead_path = self.path.parent / "keys_dead.json"
        archive: list[dict] = []
        if dead_path.exists():
            try:
                raw = json.loads(dead_path.read_text(encoding="utf-8"))
                archive = raw.get("keys", []) if isinstance(raw, dict) else raw
            except (json.JSONDecodeError, UnicodeDecodeError):
                archive = []
        # never store the same dead key twice
        if any(k.get("value") == key.value for k in archive):
            return
        archive.append({
            "value": key.value,
            "service": key.service,
            "masked": key.masked,
            "reason": key.reason,
            "added": getattr(key, "added", 0),
            "died_at": time.time(),
            "uses": getattr(key, "uses", 0),
            "fails": getattr(key, "fails", 0),
        })
        atomic_write_json(dead_path, {
            "version": 1,
            "saved": time.time(),
            "count": len(archive),
            "keys": archive,
        })

    def mark_exhausted(self, value: str, reason: str = "rate limited") -> None:
        key = self.find(value)
        if key is None:
            return
        key.state = EXHAUSTED
        key.reason = reason
        key.last_checked = time.time()
        self.save()
        log.warn(f"{key.service} key {key.masked} exhausted ({reason}) - advancing")

    def mark_alive(self, value: str) -> None:
        key = self.find(value)
        if key is None:
            return
        key.state = ALIVE
        key.reason = ""
        key.last_checked = time.time()
        key.uses += 1
        self.save()

    # -- editing

    def add(self, service: str, value: str) -> Key:
        if len(self._keys) >= self.max_keys:
            raise ValueError(f"key limit reached ({self.max_keys})")
        if self.find(value) is not None:
            raise ValueError("that key is already on file")
        key = Key(value=value.strip(), service=service)
        self._keys.append(key)
        self.save()
        return key

    def import_lines(self, text: str) -> tuple[int, int, list[str]]:
        """
        Pull keys out of pasted text or an existing env file.

        This parses text; it never copies a file. Nothing from an old project
        is opened, imported or moved - only the key values are read, which are
        yours and belong to no build.

        Recognises lines shaped like:

            PEXELS_API_KEY=abc123
            GEMINI_API_KEY_2 = xyz789
            export GROQ_KEY=...

        Returns (added, skipped, notes).
        """
        import re

        service_hints = {
            "PEXELS": "pexels",
            "PIXABAY": "pixabay",
            "GROQ": "groq",
            "GEMINI": "gemini",
            "GOOGLE": "gemini",
        }

        added = 0
        skipped = 0
        notes: list[str] = []

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            name = name.strip()
            if name.lower().startswith("export "):
                name = name[7:].strip()
            value = value.strip().strip('"').strip("'")

            if not value or value.lower() in {"your_key_here", "changeme", "none", "null"}:
                continue

            upper = name.upper()
            service = next((svc for hint, svc in service_hints.items() if hint in upper), None)
            if service is None:
                notes.append(f"skipped '{name}' - cannot tell which service it belongs to")
                skipped += 1
                continue

            if self.find(value) is not None:
                skipped += 1
                continue

            if len(self._keys) >= self.max_keys:
                notes.append(f"stopped at the {self.max_keys}-key limit")
                break

            self._keys.append(Key(value=value, service=service))
            added += 1

        if added:
            self.save()
        return added, skipped, notes

    def remove(self, value: str) -> bool:
        """
        Present for completeness but blocked by default: the never-delete rule
        is deliberate, so removal must be explicit.
        """
        if self.never_delete:
            raise PermissionError(
                "never_delete is on. Dead keys stay on file by design. "
                "Set never_delete=false in config to override."
            )
        before = len(self._keys)
        self._keys = [k for k in self._keys if k.value != value]
        if len(self._keys) != before:
            self.save()
            return True
        return False
