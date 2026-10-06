"""
ANTAR - run state.

Holds the two things that must survive between videos:

  1. The rotation cursor. Which template values are due next, and what the
     previous video used. This is the defence against YouTube's
     anti-repetitive-content filter.

  2. The render counter. ANTAR_0001, ANTAR_0002 ... no version suffixes,
     ever, because a version suffix is how two builds end up running at once.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import log
from .vault import atomic_write_json


class Rotation:
    """
    Cycles template values so consecutive videos differ.

    Rule from config: no two consecutive videos may share more than 3 of the
    11 rotating values.
    """

    def __init__(self, options: dict[str, list], max_shared: int = 3):
        self.options = options
        self.max_shared = max_shared
        self.cursor: dict[str, int] = {k: 0 for k in options}

    def advance(self, previous: dict[str, str] | None = None) -> dict[str, str]:
        """
        Produce the next combination.

        Steps each cursor forward, then checks the overlap rule against the
        previous video and keeps stepping the offenders until the rule holds.
        """
        choice: dict[str, str] = {}
        for name, values in self.options.items():
            if not values:
                continue
            idx = self.cursor.get(name, 0) % len(values)
            choice[name] = values[idx]

        if previous:
            guard = 0
            while guard < 50:
                shared = [k for k, v in choice.items()
                          if previous.get(k) is not None and previous.get(k) == v]
                if len(shared) <= self.max_shared:
                    break
                # step only the offending variables, one place each
                for name in shared[:len(shared) - self.max_shared]:
                    values = self.options.get(name) or []
                    if not values:
                        continue
                    self.cursor[name] = (self.cursor.get(name, 0) + 1) % len(values)
                    choice[name] = values[self.cursor[name]]
                guard += 1
            if len(shared) > self.max_shared:
                log.warn("rotation could not fully separate this video from the last one")

        # commit the cursors
        for name, values in self.options.items():
            if values:
                self.cursor[name] = (self.cursor.get(name, 0) + 1) % len(values)
        self.last = choice
        return choice

    def shared_with(self, other: dict[str, str]) -> list[str]:
        return [k for k, v in (getattr(self, "last", {}) or {}).items()
                if other.get(k) is not None and other.get(k) == v]


class RunState:
    """config/state/state.json - the small file that survives between runs."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.data: dict = {
            "render_counter": 0,
            "last_rotation": {},
            "last_render": None,
            "history": [],
        }
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            log.warn(f"state unreadable, starting fresh: {exc}")

    def save(self) -> None:
        atomic_write_json(self.path, self.data)

    # -- render ids: ANTAR_0007_<slug>.mp4, never ANTAR_v2_...

    def next_render_id(self, slug: str = "") -> str:
        self.data["render_counter"] = int(self.data.get("render_counter", 0)) + 1
        number = self.data["render_counter"]
        clean = "".join(ch for ch in slug if ch.isalnum() or ch in "-_")[:40]
        self.save()
        return f"ANTAR_{number:04d}_{clean}" if clean else f"ANTAR_{number:04d}"

    # -- rotation memory

    def previous_rotation(self) -> dict:
        return self.data.get("last_rotation", {}) or {}

    def commit_rotation(self, choice: dict) -> None:
        self.data["last_rotation"] = choice
        self.save()

    # -- history

    def record(self, entry: dict) -> None:
        history = self.data.setdefault("history", [])
        entry["at"] = time.time()
        history.append(entry)
        self.data["history"] = history[-200:]
        self.data["last_render"] = entry
        self.save()

    def history(self) -> list[dict]:
        return self.data.get("history", [])
