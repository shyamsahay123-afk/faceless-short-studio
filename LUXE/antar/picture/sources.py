"""
ANTAR - asking a stock library for footage.

Two free libraries, Pexels first and Pixabay behind it. Both give away the
footage for anything, including commercial use, with no fee and no credit
required. Neither is ever called without a key, and neither is called with a
key that has been written off.

Every request carries a browser user agent. This is not politeness: Groq and
Pexels both sit behind Cloudflare, which answers 403 "error code: 1010" to
Python's default agent. That is what made four working Pexels keys look dead.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .. import log
from ..probe import COMMON_HEADERS
from ..vault import find_ffmpeg

SERVICES = ("pexels", "pixabay")

PEXELS_SEARCH = "https://api.pexels.com/videos/search"
PIXABAY_SEARCH = "https://pixabay.com/api/videos/"

TIMEOUT = 25


class SourceError(RuntimeError):
    """
    The library could not be asked. The caller must say so, not guess.

    Carries the status code so the key ring can tell a dead key from a rate
    limit from a block without reading the message back like a human would.
    """

    def __init__(self, message: str, status: int = 0, service: str = ""):
        super().__init__(message)
        self.status = status
        self.service = service


@dataclass
class Candidate:
    """One downloadable clip, offered by a library."""

    source: str
    id: str
    query: str
    file_url: str
    width: int
    height: int
    duration: float
    page_url: str = ""
    files: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def portrait(self) -> bool:
        return self.height > self.width

    @property
    def megapixels(self) -> float:
        return (self.width * self.height) / 1_000_000

    @property
    def key(self) -> str:
        return f"{self.source}:{self.id}"

    @property
    def description(self) -> str:
        """What the library says this clip is, in words. Usually the page slug."""
        from .faces import slug_words

        return slug_words(self.page_url) or self.query


def _get(url: str, headers: dict) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={**COMMON_HEADERS, **headers})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, exc.read().decode("utf-8", "replace")
        except Exception:
            return exc.code, str(exc.reason or "")
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}"


def _pick_file(files: list[dict], min_height: int,
               prefer_height: int = 1920) -> dict | None:
    """
    The file to actually download.

    First choice is the smallest file that is at least `prefer_height` tall -
    on Pexels that lands on 1080x1920, which is the canvas. A 720-wide clip
    stretched to 1080 is soft, and softness is exactly what makes cheap stock
    footage look cheap. Only when a clip has nothing that big do we take the
    biggest one it has, so a smaller file is a last resort rather than the
    default.
    """
    portrait = [f for f in files
                if f.get("width") and f.get("height")
                and f["height"] > f["width"] and f.get("link")]
    if not portrait:
        return None
    hd = [f for f in portrait if f["height"] >= prefer_height]
    if hd:
        return min(hd, key=lambda f: (f["height"], f["width"]))
    wide_enough = [f for f in portrait if f["height"] >= min_height]
    pool = wide_enough or portrait
    return max(pool, key=lambda f: (f["height"], f["width"]))


def _pexels(key: str, query: str, per_page: int, min_height: int,
            prefer_height: int = 1920) -> list[Candidate]:
    url = (f"{PEXELS_SEARCH}?query={urllib.parse.quote(query)}"
           f"&per_page={per_page}&orientation=portrait")
    status, body = _get(url, {"Authorization": key})
    if status != 200:
        raise SourceError(f"pexels said {status or 'nothing'}: {body[:160]}",
                          status=status, service="pexels")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SourceError(f"pexels sent something that is not JSON: {body[:120]}",
                          status=status, service="pexels") from exc

    out: list[Candidate] = []
    for video in payload.get("videos", []):
        chosen = _pick_file(video.get("video_files", []), min_height, prefer_height)
        if not chosen:
            continue
        out.append(Candidate(
            source="pexels",
            id=str(video.get("id", "")),
            query=query,
            file_url=chosen["link"],
            width=int(chosen["width"]),
            height=int(chosen["height"]),
            duration=float(video.get("duration", 0) or 0),
            page_url=str(video.get("url", "")),
            files=len(video.get("video_files", [])),
        ))
    return out


def _pixabay(key: str, query: str, per_page: int, min_height: int,
             prefer_height: int = 1920) -> list[Candidate]:
    url = (f"{PIXABAY_SEARCH}?key={urllib.parse.quote(key)}"
           f"&q={urllib.parse.quote(query)}&per_page={max(3, per_page)}")
    status, body = _get(url, {})
    if status != 200:
        raise SourceError(f"pixabay said {status or 'nothing'}: {body[:160]}",
                          status=status, service="pixabay")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SourceError(f"pixabay sent something that is not JSON: {body[:120]}",
                          status=status, service="pixabay") from exc

    out: list[Candidate] = []
    for video in payload.get("hits", []):
        renditions = video.get("videos", {})
        options = []
        for name, item in renditions.items():
            if item.get("url") and item.get("width") and item.get("height"):
                options.append({"link": item["url"], "width": item["width"],
                                "height": item["height"], "quality": name})
        chosen = _pick_file(options, min_height, prefer_height)
        if not chosen:
            continue
        out.append(Candidate(
            source="pixabay",
            id=str(video.get("id", "")),
            query=query,
            file_url=chosen["link"],
            width=int(chosen["width"]),
            height=int(chosen["height"]),
            duration=float(video.get("duration", 0) or 0),
            page_url=str(video.get("pageURL", "")),
            files=len(options),
        ))
    return out


def search(service: str, key: str, query: str, per_page: int = 15,
           min_height: int = 1280, prefer_height: int = 1920) -> list[Candidate]:
    """Ask one library for one query. Raises SourceError with what it said."""
    if service not in SERVICES:
        raise SourceError(f"no library called '{service}'")
    if not key:
        raise SourceError(f"no {service} key on file")
    if service == "pexels":
        return _pexels(key, query, per_page, min_height, prefer_height)
    return _pixabay(key, query, per_page, min_height, prefer_height)


def download(candidate: Candidate, dest_dir: Path, *, max_mb: float = 25.0) -> Path:
    """
    Pull one clip down. The size cap is checked while reading, not after, so a
    surprise 200MB file cannot land on the disk first.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(urllib.parse.urlparse(candidate.file_url).path).suffix or ".mp4"
    dest = dest_dir / f"{candidate.source}-{candidate.id}{suffix}"

    request = urllib.request.Request(candidate.file_url, headers=COMMON_HEADERS)
    limit = int(max_mb * 1024 * 1024)
    written = 0
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT * 4) as response:
            with open(dest, "wb") as handle:
                while True:
                    block = response.read(262_144)
                    if not block:
                        break
                    written += len(block)
                    if written > limit:
                        handle.close()
                        dest.unlink(missing_ok=True)
                        raise SourceError(
                            f"the clip is bigger than the {max_mb:.0f}MB cap - skipped")
                    handle.write(block)
    except SourceError:
        raise
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise SourceError(f"download failed: {type(exc).__name__}: {exc}") from exc

    if written == 0:
        dest.unlink(missing_ok=True)
        raise SourceError("the library sent an empty file")

    return dest


def probe_clip(path: Path) -> dict:
    """Read a downloaded clip's real numbers, rather than trusting the listing."""
    ff = find_ffmpeg()
    if not ff:
        return {}
    import re
    import subprocess

    result = subprocess.run([ff, "-hide_banner", "-i", str(path)],
                            capture_output=True, text=True)
    text = result.stderr
    info: dict = {"bytes": Path(path).stat().st_size}

    match = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", text)
    if match:
        info["seconds"] = (int(match.group(1)) * 3600 + int(match.group(2)) * 60
                           + float(match.group(3)))
    match = re.search(r",\s*(\d+)x(\d+)[\s,]", text)
    if match:
        info["width"], info["height"] = int(match.group(1)), int(match.group(2))
    match = re.search(r",\s*([\d.]+)\s*fps", text)
    if match:
        info["fps"] = float(match.group(1))
    return info
