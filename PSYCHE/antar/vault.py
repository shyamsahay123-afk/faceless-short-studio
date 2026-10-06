"""
ANTAR - the vault.

A 5GB local clip cache that enforces the two rules the old engine broke:

  Rule 1  A clip may be used at most twice, ever.
  Rule 2  Lookalike clips count as the same clip.

Both were broken before because the registry was keyed by filename, and
filenames are random. Here every clip is keyed by a content hash, and a
perceptual signature catches re-encodes and near-duplicates.

The perceptual signature needs Pillow and ffmpeg. If either is missing the
vault still works - it simply falls back to content hashing alone and says so.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import log

CHUNK = 1024 * 1024


# ---------------------------------------------------------------- helpers

def atomic_write_json(path: Path, data) -> None:
    """Write JSON so a crash can never leave a half-written registry."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def content_hash(path: Path, sample_bytes: int = 2 * CHUNK) -> str:
    """
    Hash a clip without reading the whole file.

    size + first 2MB is enough to separate two different clips and is stable
    across re-downloads of the same clip. Kept fast because the vault may hold
    hundreds of files.
    """
    size = path.stat().st_size
    h = hashlib.sha256()
    h.update(str(size).encode())
    with path.open("rb") as fh:
        h.update(fh.read(sample_bytes))
        if size > sample_bytes * 2:
            fh.seek(-sample_bytes, os.SEEK_END)
            h.update(fh.read(sample_bytes))
    return h.hexdigest()[:32]


def find_ffmpeg() -> str | None:
    """
    Locate an ffmpeg binary, in the order that fails least often:

      1. ANTAR_FFMPEG         an explicit override, always wins
      2. PATH                 a system install
      3. imageio-ffmpeg       the known-good binary shipped by requirements.txt

    Step 3 matters: imageio-ffmpeg is a listed dependency, so a plain
    'pip install -r requirements.txt' produces a working engine even on a
    machine where ffmpeg was never added to PATH.
    """
    override = os.environ.get("ANTAR_FFMPEG")
    if override and Path(override).exists():
        return override

    found = shutil.which("ffmpeg")
    if found:
        return found

    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def perceptual_signature(path: Path, ffmpeg: str | None = None) -> str | None:
    """
    64-bit difference hash of one frame, as a hex string.

    Two clips of the same footage at different bitrates or resolutions produce
    the same or a near-identical signature, which is what makes the
    'lookalike counts as a repeat' rule enforceable.

    Returns None if Pillow or ffmpeg is unavailable - the caller must treat a
    missing signature as 'unknown', never as 'unique'.
    """
    ffmpeg = ffmpeg or find_ffmpeg()
    if not ffmpeg:
        return None
    try:
        from PIL import Image  # noqa: WPS433 (optional dependency)
    except ImportError:
        return None

    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        result = subprocess.run(
            [ffmpeg, "-v", "error", "-y", "-i", str(path),
             "-vf", "select=eq(n\\,20),scale=9:8", "-frames:v", "1", tmp],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0 or not os.path.getsize(tmp):
            return None
        img = Image.open(tmp).convert("L")
        px = list(img.getdata())
        bits = 0
        for row in range(8):
            base = row * 9
            for col in range(8):
                bits = (bits << 1) | (1 if px[base + col] > px[base + col + 1] else 0)
        return f"{bits:016x}"
    except Exception:
        return None
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def hamming(a: str, b: str) -> int:
    """Bit distance between two hex signatures."""
    if not a or not b:
        return 999
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except ValueError:
        return 999


# ---------------------------------------------------------------- the vault

@dataclass
class Clip:
    hash: str
    filename: str
    path: str
    bytes: int
    uses: int = 0
    first_seen: float = field(default_factory=time.time)
    last_used: float = 0.0
    source: str = ""
    query: str = ""
    signature: str | None = None
    width: int = 0
    height: int = 0
    duration: float = 0.0
    used_in: list[str] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return self.uses < 2


class Vault:
    def __init__(self, root: Path, cap_gb: float = 5.0, max_uses: int = 2,
                 lookalike_distance: int = 4, registry_name: str = "registry.json"):
        self.root = Path(root)
        self.clips_dir = self.root / "clips"
        self.clips_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.root / registry_name
        self.cap_bytes = int(cap_gb * 1024 ** 3)
        self.max_uses = max_uses
        self.lookalike_distance = lookalike_distance
        self._clips: dict[str, Clip] = {}
        self._signature_warned = False
        self.load()

    # -- persistence

    def load(self) -> None:
        if not self.registry_path.exists():
            self._clips = {}
            return
        try:
            raw = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            log.warn(f"vault registry unreadable, starting empty: {exc}")
            self._clips = {}
            return
        self._clips = {}
        for key, payload in raw.get("clips", {}).items():
            try:
                self._clips[key] = Clip(**payload)
            except TypeError:
                log.warn(f"vault entry ignored (unexpected fields): {key}")

    def save(self) -> None:
        atomic_write_json(self.registry_path, {
            "version": 1,
            "saved": time.time(),
            "total_bytes": self.total_bytes,
            "clips": {k: asdict(v) for k, v in self._clips.items()},
        })

    # -- queries

    @property
    def total_bytes(self) -> int:
        return sum(c.bytes for c in self._clips.values())

    @property
    def total_gb(self) -> float:
        return self.total_bytes / 1024 ** 3

    def __len__(self) -> int:
        return len(self._clips)

    def get(self, content: str) -> Clip | None:
        return self._clips.get(content)

    def all(self) -> list[Clip]:
        return list(self._clips.values())

    def is_repeat(self, content: str, signature: str | None = None) -> tuple[bool, str]:
        """
        Would using this clip break a rule?
        Returns (True, reason) or (False, "").
        """
        clip = self._clips.get(content)
        if clip is not None and clip.uses >= self.max_uses:
            return True, f"used {clip.uses}x (limit {self.max_uses})"

        if signature:
            for other in self._clips.values():
                if other.uses == 0 or not other.signature:
                    continue
                if other.hash == content:
                    continue
                distance = hamming(signature, other.signature)
                if distance <= self.lookalike_distance:
                    return True, (
                        f"lookalike of {other.filename[:40]} "
                        f"(distance {distance}, limit {self.lookalike_distance})"
                    )
        return False, ""

    # -- mutation

    def add(self, source_path: Path, source: str = "", query: str = "",
            meta: dict | None = None) -> Clip:
        """Copy a downloaded clip in, keyed by its content hash."""
        source_path = Path(source_path)
        meta = meta or {}
        content = content_hash(source_path)
        signature = perceptual_signature(source_path)
        if signature is None and not self._signature_warned:
            log.warn("perceptual signatures unavailable - lookalike detection is OFF "
                     "(install Pillow and ffmpeg to enable it)")
            self._signature_warned = True

        suffix = source_path.suffix or ".mp4"
        target = self.clips_dir / f"{content}{suffix}"

        if content in self._clips:
            existing = self._clips[content]
            if not Path(existing.path).exists():
                shutil.copy2(source_path, target)
                existing.path = str(target)
            return existing

        if not target.exists():
            shutil.copy2(source_path, target)

        clip = Clip(
            hash=content,
            filename=target.name,
            path=str(target),
            bytes=target.stat().st_size,
            source=source,
            query=query,
            signature=signature,
            width=int(meta.get("width", 0) or 0),
            height=int(meta.get("height", 0) or 0),
            duration=float(meta.get("duration", 0) or 0),
        )
        self._clips[content] = clip
        self.save()
        return clip

    def record_use(self, content: str, video_id: str = "") -> Clip:
        """
        Count one use. Twice at most, ever.

        A use is a VIDEO, not a run. Running the same render again - to fix a
        line, to change a grade - is the same video, and counting it again
        would spend a clip's second life on a re-run. Observed happening: a
        second run of the same shot plan pushed six clips to 2/2.
        """
        clip = self._clips[content]
        if video_id and video_id in clip.used_in:
            clip.last_used = time.time()
            self.save()
            return clip
        clip.uses += 1
        clip.last_used = time.time()
        if video_id and video_id not in clip.used_in:
            clip.used_in.append(video_id)
        self.save()
        return clip

    def unused(self) -> list[Clip]:
        return [c for c in self._clips.values() if c.available]

    # -- housekeeping

    def prune(self, protect_hashes: set[str] | None = None) -> int:
        """
        Drop the least recently used clips until the vault is under cap.
        Never removes a clip that is protected or already used.
        Returns the number of clips removed.
        """
        protect = protect_hashes or set()
        removed = 0
        while self.total_bytes > self.cap_bytes and self._clips:
            candidates = [c for c in self._clips.values()
                          if c.hash not in protect and c.uses == 0]
            if not candidates:
                candidates = [c for c in self._clips.values() if c.hash not in protect]
            if not candidates:
                break
            victim = min(candidates, key=lambda c: (c.last_used, c.first_seen))
            try:
                Path(victim.path).unlink(missing_ok=True)
            except OSError as exc:
                log.warn(f"could not delete {victim.filename}: {exc}")
            self._clips.pop(victim.hash, None)
            removed += 1
        if removed:
            self.save()
        return removed

    def verify(self) -> list[str]:
        """Return a list of problems: registry entries whose file is gone."""
        missing = []
        for clip in self._clips.values():
            if not Path(clip.path).exists():
                missing.append(clip.hash)
        return missing
