"""
ANTAR - the shot plan.

Turns a finished script into the list of things that will be on screen, in
order, with the seconds each one holds for.

    beat 0  फ़ोन     clip   vault/clips/3f9a....mp4   pexels 1080x1920  4.2s
    beat 1  मग      clip   vault/clips/81be....mp4   pexels 1080x1920  3.8s
    beat 2  दीवार   card   output/cards/..._02.png   drawn here        3.1s

The seconds come from the voice stage. Phase 3 saved where every word lands in
the finished audio; the beats are split into words in the same order, so each
shot gets the real screen time of the line it belongs to, not an average. If
the word counts do not line up the plan says so and falls back, because a wrong
number that looks right is worse than no number.

A beat with no usable clip gets a card. That is not a failure path - it is a
designed outcome, and the plan records why it happened so the run can be read
afterwards without guessing.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .. import log
from ..brain import objects as object_table
from ..keys import AllKeysDown
from ..vault import Vault, atomic_write_json, content_hash, perceptual_signature
from . import card as card_mod
from . import choose, sources
from .faces import faces_available, scan_for_faces, why_unavailable


class PictureError(RuntimeError):
    """The stage could not run at all - no script, or no beats in it."""


@dataclass
class Shot:
    index: int
    role: str
    line_hi: str
    object_hi: str = ""
    query: str = ""
    kind: str = "card"
    path: str = ""
    source: str = ""
    clip_id: str = ""
    width: int = 0
    height: int = 0
    seconds: float = 0.0
    start: float = 0.0
    end: float = 0.0
    hold: float = 0.0
    speech: float = 0.0
    brightness: float = 0.0
    black_pct: float = 0.0
    bytes: int = 0
    uses: int = 0
    faces: int = 0
    face_scan: bool = False
    poster: str = ""
    grade_name: str = "neutral-grey-green"
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def beat_windows(take: dict | None, beat_lines: list[str],
                 total_seconds: float = 0.0) -> tuple[list[dict], str]:
    """
    Where each beat sits on the finished timeline.

    Returns (windows, note); each window is {"start", "end", "speech"} in
    seconds of the FINISHED track. start and end are absolute, so a cut lands
    on the same frame the voice does - a list of lengths alone drifts, because
    every pause between beats is missing from it.

    The windows run first-word to first-word: the trailing silence of a beat
    belongs to the shot already on screen, and the 0.85s before the payoff
    belongs to the beat before the payoff. Nothing is left uncovered.

    speech is only the part the voice is actually speaking, and the note says
    which way it was all worked out, so a fallback never reads as a
    measurement.
    """
    count = len(beat_lines)
    if not count:
        return [], "no beats"

    words = (take or {}).get("word_timings") or []
    if words:
        spoken = [len(str(line).split()) for line in beat_lines]
        if sum(spoken) == len(words):
            windows = []
            bounds = []
            cursor = 0
            for n in spoken:
                chunk = words[cursor:cursor + n]
                cursor += n
                bounds.append((chunk[0]["start"], chunk[-1]["end"]))
            for i, (first, last) in enumerate(bounds):
                start = 0.0 if i == 0 else first
                end = bounds[i + 1][0] if i + 1 < len(bounds) else (
                    total_seconds or last)
                windows.append({
                    "start": round(start, 3),
                    "end": round(max(start + 0.6, end), 3),
                    "speech": round(max(0.6, last - first), 3),
                })
            return windows, (f"measured from the voice, word for word "
                             f"({len(words)} words over {count} beats)")

        step = (total_seconds / count) if total_seconds else 2.5
        return ([{"start": round(i * step, 3), "end": round((i + 1) * step, 3),
                  "speech": round(step, 3)} for i in range(count)],
                f"split evenly - {len(words)} word times against "
                f"{sum(spoken)} words of script")

    if total_seconds:
        step = total_seconds / count
        return ([{"start": round(i * step, 3), "end": round((i + 1) * step, 3),
                  "speech": round(step, 3)} for i in range(count)],
                "split evenly across the audio")
    return ([{"start": round(i * 2.5, 3), "end": round((i + 1) * 2.5, 3),
              "speech": 2.5} for i in range(count)],
            "assumed 2.5s a beat - the voice has not been run for this script")


def _card_word(line: str, fallback: str) -> str:
    """A word for the card when the line names no object at all."""
    found = object_table.objects_in(line)
    if found:
        return found[0]
    words = [w.strip("।,.!?") for w in (line or "").split()]
    words = [w for w in words if len(w) > 3]
    return words[-1] if words else (fallback or "ANTAR")


def _services_with_keys(ring, preferred: str) -> list[tuple[str, str]]:
    """(service, key) pairs worth trying, preferred library first.
    
    PREMIUM FIX: Only return ALIVE keys, not UNKNOWN. Unknown keys are often
    fake/test keys that cause 25s timeout per key (hang). If no alive keys,
    return empty so vault fallback triggers immediately (premium clips).
    """
    if ring is None:
        return []
    order = [preferred] + [s for s in sources.SERVICES if s != preferred]
    pairs: list[tuple[str, str]] = []
    for service in order:
        try:
            # Try to get an ALIVE key first, not just any unknown
            alive_keys = [k for k in ring.for_service(service) if k.state == "alive"]
            if alive_keys:
                # Use first alive not tried this run
                for k in alive_keys:
                    if k.value not in ring._tried_this_run:
                        ring._tried_this_run.add(k.value)
                        pairs.append((service, k.value))
                        break
            else:
                # No alive keys - don't return unknown fake keys that cause hang
                # Let vault fallback handle it (premium)
                continue
        except Exception:
            continue
    return pairs


def _find(candidates_source, pairs, query: str, *, per_page: int,
          min_height: int, prefer_height: int, ring, notes: list[str]) -> list:
    """Ask each library that has a usable key, until one answers."""
    for service, key in pairs:
        try:
            return list(candidates_source(service, key, query, per_page=per_page,
                                          min_height=min_height,
                                          prefer_height=prefer_height))
        except sources.SourceError as exc:
            notes.append(f"{service}: {exc}")
            status = getattr(exc, "status", 0)
            if key:
                if status == 401:
                    ring.mark_dead(key, f"{status} on video search")
                elif status == 429:
                    ring.mark_exhausted(key, "429 on video search")
        except Exception as exc:
            notes.append(f"{service}: {type(exc).__name__}: {exc}")
    return []


def build_plan(config, payload: dict, *, ring=None, voice: dict | None = None,
               source=None, seed: str = "", service: str = "pexels",
               offline: bool = False) -> dict:
    """
    Build the shot plan for one script.

    `source` is the search function to use, with the same signature as
    sources.search. Tests pass a fake; a real run leaves it alone.
    """
    script = payload.get("script") or {}
    beats = script.get("beats") or []
    if not beats:
        raise PictureError("the script has no beats - nothing to find pictures for")

    render_id = payload.get("render_id") or "ANTAR_UNKNOWN"
    output_dir = config.path("paths.output")
    cards_dir = output_dir / "cards"
    frames_dir = output_dir / "frames"
    cache_dir = output_dir / "downloads"

    vault = Vault(config.path("paths.vault"),
                  cap_gb=float(config["vault.cap_gb"]),
                  max_uses=int(config["vault.max_uses_per_clip"]),
                  lookalike_distance=int(config["vault.lookalike_hamming_distance"]))

    search = source or sources.search
    beat_lines = [str(b.get("line_hi", "")) for b in beats]
    windows, timing_note = beat_windows(
        voice, beat_lines, float((voice or {}).get("track", {}).get("seconds", 0) or 0))

    min_height = int(config.get("picture.min_height", 1280))
    prefer_height = int(config.get("picture.prefer_height", 1920))
    per_page = int(config.get("picture.per_page", 15))
    target = float(config.get("picture.target_seconds", 4.0))
    minimum = float(config.get("picture.min_seconds", 3.0))
    max_mb = float(config.get("picture.max_download_mb", 25.0))
    want_face_scan = bool(config.get("picture.face_scan", True)) and faces_available()
    # "no frame mostly black" is a blocking rule. The picture stage is where a
    # black clip can still be avoided cheaply, so the frame is measured here
    # too - a grade cannot recover a picture that was never in the file.
    black_limit = float(config.get("thresholds.darkest_frame_max_black_pct", 55))

    pairs = [] if (offline or source is not None) else _services_with_keys(ring, service)
    if not offline and source is None and not pairs:
        log.warn("no stock-library key is alive - will try vault clips first, then text cards")
        log.info("add one with: python run.py keys add pexels <key> - vault has "
                 f"{len(vault)} clips as fallback")

    # grade rotation: walk through warm/cold/neutral/teal by beat so consecutive
    # shots don't all look like they came out of the same bath. The starting grade
    # comes from the project's rotation so consecutive videos differ too.
    from ..state import Rotation, RunState
    _state = RunState(config.path("paths.state") / "state.json")
    _rot = Rotation(config.get("rotation.rotating", {}))
    _rotation = _rot.advance(_state.previous_rotation() or None)
    _start_grade = _rotation.get("grade", "neutral-grey-green")
    _all_grades = ["warm-amber", "cold-blue", "neutral-grey-green", "desaturated-teal"]
    if _start_grade in _all_grades:
        _start_idx = _all_grades.index(_start_grade)
    else:
        _start_idx = 0

    used_keys: set[str] = set()
    shots: list[Shot] = []
    downloads = rejected = 0
    fresh: set[str] = set()
    # object -> the shot that already used it, so the same thing coming back
    # in the same video comes back as the same picture
    already: dict[str, Shot] = {}

    for index, beat in enumerate(beats):
        line = beat_lines[index]
        hint = str(beat.get("object_hi", ""))
        window = windows[index] if index < len(windows) else {
            "start": 0.0, "end": 0.0, "speech": 0.0}
        shot = Shot(index=index, role=str(beat.get("role", "")), line_hi=line,
                    object_hi=hint,
                    start=window["start"], end=window["end"],
                    hold=round(window["end"] - window["start"], 3),
                    speech=window["speech"],
                    face_scan=want_face_scan,
                    grade_name=_all_grades[(_start_idx + index) % len(_all_grades)])

        resolved = object_table.resolve(line, hint)
        if resolved:
            shot.query = resolved[0]
        else:
            shot.notes.append("the line names no object the table knows - card it is")

        got_clip = False

        # A beat that returns to an object it already showed gets the very same
        # shot back. Running the search again pictures it twice with two
        # different clips, which reads as an accident - and in a looping script
        # the return is the point. It also costs no download and burns no use.
        earlier = already.get(shot.query) if shot.query else None
        if earlier is not None and earlier.kind == "clip":
            shot.kind = "clip"
            shot.path = earlier.path
            shot.source = earlier.source
            shot.clip_id = earlier.clip_id
            shot.width, shot.height = earlier.width, earlier.height
            shot.seconds, shot.bytes = earlier.seconds, earlier.bytes
            shot.uses = earlier.uses
            shot.poster = earlier.poster
            shot.brightness = earlier.brightness
            shot.black_pct = earlier.black_pct
            shot.face_scan = earlier.face_scan
            shot.notes.append(f"the same shot as beat {earlier.index}, on purpose - "
                              f"the line comes back to it")
            shots.append(shot)
            continue

        # PREMIUM FIX: If no API keys, try vault clips directly before falling to cards
        # This prevents "plain bg for seconds" when vault has 7 premium clips
        if not got_clip and (offline or not pairs) and not source:
            try:
                vault_clips = vault.all()  # List[Clip]
            except Exception:
                vault_clips = []
            if vault_clips:
                import hashlib
                from pathlib import Path as _P
                idx = int(hashlib.blake2b(f"{seed}|{render_id}|{index}".encode(),
                                          digest_size=4).hexdigest(), 16) % len(vault_clips)
                vc = vault_clips[idx]
                v_path = getattr(vc, "path", "") or ""
                if v_path and _P(v_path).exists():
                    shot.kind = "clip"
                    shot.path = str(v_path)
                    shot.source = getattr(vc, "source", "vault") or "vault"
                    shot.clip_id = getattr(vc, "hash", "")[:12]
                    shot.width = int(getattr(vc, "width", 0) or 1080)
                    shot.height = int(getattr(vc, "height", 0) or 1920)
                    shot.seconds = float(getattr(vc, "duration", 0) or 4.0)
                    shot.bytes = int(getattr(vc, "bytes", 0) or 0)
                    shot.notes.append(f"vault fallback clip {_P(v_path).name} - no API key, premium vault")
                    got_clip = True
                    if shot.query:
                        already[shot.query] = shot
                    shots.append(shot)
                    continue

        if shot.query and not offline and (pairs or source is not None):
            candidates = (_find(search, pairs, shot.query, per_page=per_page,
                                min_height=min_height, prefer_height=prefer_height,
                                ring=ring, notes=shot.notes)
                          if source is None else
                          list(search(service, "", shot.query, per_page=per_page,
                                      min_height=min_height,
                                      prefer_height=prefer_height)))

            refusals: list[str] = []
            for _attempt in range(4):
                chosen, refusals = choose.pick(
                    candidates, used_keys=used_keys, target_seconds=target,
                    min_seconds=minimum, seed=f"{seed}|{render_id}|{index}")
                if not chosen:
                    shot.notes.extend(refusals[-3:])
                    break

                used_keys.add(chosen.key)
                try:
                    local = sources.download(chosen, cache_dir, max_mb=max_mb)
                except sources.SourceError as exc:
                    shot.notes.append(f"{chosen.key}: {exc}")
                    rejected += 1
                    continue

                content = content_hash(local)
                signature = perceptual_signature(local)
                repeated, why = vault.is_repeat(content, signature)
                if repeated:
                    shot.notes.append(f"{chosen.key} refused - {why}")
                    local.unlink(missing_ok=True)
                    rejected += 1
                    continue

                # the clip is read before it is scanned, so the scan uses its
                # real length rather than the length the listing claimed
                probe = sources.probe_clip(local)
                faces, at = ((0, []) if not want_face_scan else
                             scan_for_faces(local, float(probe.get("seconds")
                                                         or chosen.duration or 0)))
                if faces:
                    shot.notes.append(f"{chosen.key} thrown away - a face at {at}s")
                    local.unlink(missing_ok=True)
                    rejected += 1
                    continue

                poster = _poster(Path(local), frames_dir, render_id, index,
                                 float(probe.get("seconds") or chosen.duration or 0))
                black_pct = card_mod.frame_black_pct(poster)
                if black_pct > black_limit:
                    shot.notes.append(
                        f"{chosen.key} thrown away - {black_pct:.0f}% of the frame is "
                        f"black (limit {black_limit:.0f}%)")
                    poster.unlink(missing_ok=True)
                    local.unlink(missing_ok=True)
                    rejected += 1
                    continue

                clip = vault.add(local, source=chosen.source, query=chosen.query,
                                 meta={"id": chosen.id, "page": chosen.page_url,
                                       "width": probe.get("width", chosen.width),
                                       "height": probe.get("height", chosen.height),
                                       "duration": probe.get("seconds", chosen.duration)})
                clip = vault.record_use(clip.hash, render_id)
                fresh.add(clip.hash)
                downloads += 1

                shot.kind = "clip"
                shot.path = clip.path
                shot.source = chosen.source
                shot.clip_id = chosen.id
                shot.width = int(probe.get("width") or chosen.width)
                shot.height = int(probe.get("height") or chosen.height)
                shot.seconds = float(probe.get("seconds") or chosen.duration or 0)
                shot.bytes = int(probe.get("bytes") or 0)
                shot.uses = int(clip.uses)
                shot.faces = faces
                shot.poster = str(poster)
                shot.brightness = round(card_mod.card_brightness(poster), 1)
                shot.black_pct = round(black_pct, 1)
                local.unlink(missing_ok=True)
                # keep the refusals that led here: "this one was about a person,
                # that one was a lookalike" is the record of the rule working
                shot.notes.extend(refusals[-3:])
                got_clip = True
                break

            if not got_clip and not shot.notes:
                shot.notes.append(f"nothing usable came back for '{shot.query}'")

        # SECOND VAULT FALLBACK: API search failed but vault has clips - use them
        # Prevents plain bg flash when pexels fails but vault has premium clips
        if not got_clip and not offline:
            try:
                vault_clips = vault.all()
                if vault_clips:
                    import hashlib as _hl
                    from pathlib import Path as _P2
                    idx = int(_hl.blake2b(f"{seed}|{render_id}|{index}|fallback".encode(),
                                          digest_size=4).hexdigest(), 16) % len(vault_clips)
                    vc = vault_clips[idx]
                    v_path = getattr(vc, "path", "") or ""
                    if v_path and _P2(v_path).exists():
                        shot.kind = "clip"
                        shot.path = str(v_path)
                        shot.source = getattr(vc, "source", "vault") or "vault"
                        shot.clip_id = getattr(vc, "hash", "")[:12]
                        shot.width = int(getattr(vc, "width", 0) or 1080)
                        shot.height = int(getattr(vc, "height", 0) or 1920)
                        shot.seconds = float(getattr(vc, "duration", 0) or 4.0)
                        shot.bytes = int(getattr(vc, "bytes", 0) or 0)
                        shot.notes.append(f"vault fallback after search fail - {_P2(v_path).name} premium")
                        got_clip = True
            except Exception:
                pass

        if got_clip and shot.query:
            already[shot.query] = shot

        if not got_clip:
            word = _card_word(line, hint)
            made = card_mod.build_card(word, cards_dir / f"{render_id}_{index:02d}.png",
                                       config)
            shot.kind = "card"
            shot.path = str(made.path)
            shot.width = int(config.get("canvas.width", 1080))
            shot.height = int(config.get("canvas.height", 1920))
            shot.bytes = made.path.stat().st_size
            shot.notes.append(f"text card drawn at {made.font_px}px - "
                              f"brightness {made.brightness:.1f}/255")

        shots.append(shot)

    if fresh:
        try:
            pruned = vault.prune(protect_hashes=fresh)
            if pruned:
                log.info(f"vault pruned {pruned} clip(s) to stay under the cap")
        except Exception as exc:
            log.warn(f"could not prune the vault: {exc}")

    # The synthesiser's last word mark runs about 180ms past the sound it made
    # (the voice stage already measured this and trimmed the tail). On the
    # final beat that makes the spoken time read longer than the window. The
    # window still ends where the sound ends - say it out loud, do not fudge
    # the number to make the columns match.
    if shots and shots[-1].speech > shots[-1].hold + 0.02:
        shots[-1].notes.append(
            f"the last word mark runs {shots[-1].speech - shots[-1].hold:.2f}s "
            f"past the sound - the shot ends with the sound, not the mark")

    totals = {
        "shots": len(shots),
        "clips": sum(1 for s in shots if s.kind == "clip"),
        "cards": sum(1 for s in shots if s.kind == "card"),
        "downloads": downloads,
        "rejected": rejected,
        "bytes": sum(s.bytes for s in shots),
        "seconds_covered": round(sum(s.hold for s in shots), 2),
        "timeline_end": round(max((s.end for s in shots), default=0.0), 2),
        "vault_clips": len(vault),
        "vault_gb": round(vault.total_gb, 3),
    }

    return {
        "render_id": render_id,
        "built": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seed": seed,
        "lane": config.get("lane.name", ""),
        "timing": timing_note,
        "face_scan": want_face_scan,
        "face_scan_note": ("" if want_face_scan else
                           f"off ({why_unavailable()}) - the search is people-free, "
                           f"the pixels are not checked"),
        "shots": [s.as_dict() for s in shots],
        "totals": totals,
    }


def _poster(clip_path: Path, frames_dir: Path, render_id: str, index: int,
            seconds: float) -> Path:
    """One frame from the middle of the clip, kept as proof of what was chosen."""
    import subprocess

    from ..vault import find_ffmpeg

    frames_dir.mkdir(parents=True, exist_ok=True)
    out = frames_dir / f"{render_id}_{index:02d}.jpg"
    ff = find_ffmpeg()
    if not ff:
        return out
    at = max(0.5, min((seconds or 2.0) / 2, 4.0))
    subprocess.run([ff, "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", str(clip_path),
                    "-frames:v", "1", "-q:v", "4", str(out)], capture_output=True)
    return out


def save_plan(config, plan: dict) -> Path:
    path = config.path("paths.output") / "plans" / f"{plan['render_id']}_picture.json"
    atomic_write_json(path, plan)
    return path


def load_voice(config, render_id: str) -> dict | None:
    """The voice stage's output for this render, if it has been run."""
    path = config.path("paths.output") / "audio" / f"{render_id}_audio.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
