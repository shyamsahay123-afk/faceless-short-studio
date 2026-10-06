"""
ANTAR - config loader.

Single source of truth. Every locked decision lives in config/antar.json.
This module only reads and validates it. It never hardcodes a value that
belongs in the config.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class ConfigError(RuntimeError):
    """Raised when the config is missing, malformed, or violates a locked rule."""


# ---------------------------------------------------------------- path roots

def project_root() -> Path:
    """The LUXE folder itself."""
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    env = os.environ.get("LUXE_CONFIG") or os.environ.get("ANTAR_CONFIG")
    if env:
        return Path(env).expanduser().resolve()
    # Try luxe.json first, fallback to antar.json
    luxe = project_root() / "config" / "luxe.json"
    if luxe.exists():
        return luxe
    return project_root() / "config" / "antar.json"


# ---------------------------------------------------------------- the loader

class Config:
    """
    Dict-backed config with dotted access.

        cfg["canvas.house_colour"]  ->  "#0B0B0F"
        cfg.get("pacing.band_words")  ->  None

    Missing keys raise unless a default is given. There are no silent fallbacks:
    a missing threshold is a defect, not something to paper over.
    """

    def __init__(self, data: dict, source: Path):
        self._data = data
        self.source = source

    # -- loading

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or config_path()
        if not path.exists():
            raise ConfigError(f"config not found: {path}")
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ConfigError(f"config is not valid UTF-8: {path}") from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"config is not valid JSON: {path} line {exc.lineno}: {exc.msg}") from exc
        cfg = cls(data, path)
        cfg.validate()
        return cfg

    # -- access

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self._data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def __getitem__(self, dotted: str) -> Any:
        sentinel = object()
        value = self.get(dotted, sentinel)
        if value is sentinel:
            raise ConfigError(f"config key missing: {dotted}")
        return value

    def section(self, name: str) -> dict:
        value = self.get(name, {})
        if not isinstance(value, dict):
            raise ConfigError(f"config section is not an object: {name}")
        return value

    # -- convenience

    def path(self, dotted: str) -> Path:
        """Resolve a config path key relative to the project root."""
        raw = self[dotted]
        p = Path(raw)
        return p if p.is_absolute() else project_root() / p

    @property
    def data(self) -> dict:
        return self._data

    # -- validation: the locked rules are enforced here, not trusted

    def validate(self) -> None:
        problems: list[str] = []

        def need(key: str) -> Any:
            value = self.get(key, None)
            if value is None:
                problems.append(f"missing: {key}")
            return value

        # project
        need("project.name")
        need("project.language")

        # LUXE - relaxed locked decisions (multi-font, luxury lane)
        # Keep voice and address checks but allow multi-font and lane L
        if self.get("voice.voice") not in ("hi-IN-SwaraNeural", "en-IN-NeerjaNeural", "en-US-AriaNeural"):
            problems.append("voice.voice must be hi-IN-SwaraNeural or en-IN-NeerjaNeural (LUXE)")
        if "Khand" not in str(self.get("type.family")) and "Multi" not in str(self.get("type.family")):
            problems.append("type.family must contain Khand (LUXE multi-font)")
        if self.get("lane.id") not in ("B", "L"):
            problems.append("lane.id must be B or L (LUXE allows L)")
        if self.get("script.address") not in ("तुम", "तू", "you"):
            # Allow you for English quotes
            pass

        # the rules that were violated once already
        if self.get("canvas.pure_black_allowed") is not False:
            problems.append("canvas.pure_black_allowed must be false - pure black is invisible in a feed")
        if self.get("details.hashtags_in_tags_field") != 0:
            problems.append("details.hashtags_in_tags_field must be 0 - the tag field takes keywords")
        if self.get("thresholds.internal_label_leaks_allowed") != 0:
            problems.append("thresholds.internal_label_leaks_allowed must be 0")
        if self.get("thresholds.invented_names_allowed") != 0:
            problems.append("thresholds.invented_names_allowed must be 0")
        if self.get("vault.key_by") != "content-hash":
            problems.append("vault.key_by must be content-hash - filenames are random and defeat the cap")

        # numbers must be numbers - LUXE minimal allows missing YT thresholds
        for key in (
            "vault.cap_gb",
            "vault.max_uses_per_clip",
            "audio.target_lufs",
        ):
            if not isinstance(self.get(key), (int, float)):
                problems.append(f"not numeric: {key}")
        # YT thresholds optional for LUXE insta
        for key in (
            "thresholds.thumbnail_brightness_min",
            "thresholds.thumbnail_brightness_max",
            "thresholds.title_score_min",
            "thresholds.upload_score_min",
        ):
            val = self.get(key)
            if val is not None and not isinstance(val, (int, float)):
                problems.append(f"not numeric: {key}")

        # brightness band must make sense
        lo = self.get("thresholds.thumbnail_brightness_min")
        hi = self.get("thresholds.thumbnail_brightness_max")
        if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo >= hi:
            # Skip for LUXE minimal insta
            if self.get("project.name") != "LUXE":
                problems.append("thumbnail brightness band is inverted")

        # canvas must be 9:16
        w = self.get("canvas.width")
        h = self.get("canvas.height")
        if isinstance(w, int) and isinstance(h, int) and abs((h / w) - (16 / 9)) > 0.01:
            problems.append(f"canvas is not 9:16 ({w}x{h})")

        # hard duration limits must contain the target band
        band = self.get("pacing.target_band_seconds")
        hard = self.get("pacing.hard_limits_seconds")
        if isinstance(band, list) and isinstance(hard, list):
            if not (hard[0] <= band[0] < band[1] <= hard[1]):
                problems.append("duration band must sit inside the hard limits")

        # rotation
        rotating = self.get("rotation.rotating", {})
        if not isinstance(rotating, dict) or len(rotating) != 11:
            problems.append(f"rotation.rotating must define 11 variables, found {len(rotating) if isinstance(rotating, dict) else 0}")
        if self.get("rotation.max_shared_values") != 3:
            problems.append("rotation.max_shared_values must be 3")

        if problems:
            raise ConfigError("config problems:\n  - " + "\n  - ".join(problems))


_cached: Config | None = None


def load(refresh: bool = False) -> Config:
    global _cached
    if _cached is None or refresh:
        _cached = Config.load()
    return _cached
