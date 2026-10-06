"""
PSYCHE panel - the little server underneath the page.

Standard library only: `http.server`, one thread per request, no framework, no
dependency to install on a Windows machine. It serves four things:

  * the page and the font it uses;
  * `/api/...` - the tabs' data, the job queue, scoring, saving, thumbnails;
  * `/media/...` - the render and a thumbnail, with byte ranges so the video
    scrubber in the browser works;
  * nothing else. Unknown paths get a plain 404, because a panel that serves
    the whole disk is a panel that ships your keys.

Deliberate choices worth naming:

  * `0.0.0.0`, not `127.0.0.1`. The browser that opens this panel is not always
    on this machine, and binding to loopback only is the usual reason a preview
    shows nothing.
  * no `X-Frame-Options` header and no content policy. The panel is meant to be
    embedded; a frame-blocking header would leave the operator looking at a
    blank rectangle.
  * every error comes back as JSON with a plain sentence in `error`, and the
    page prints it. A stage's failure is never swallowed into a 500 with no
    body.
"""

from __future__ import annotations

import json
import mimetypes
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import log
from . import data, jobs, thumbs
from .views import PAGE

MIME = mimetypes.MimeTypes()
VERSION = "panel-1"


def _root() -> Path:
    """The PSYCHE root, two directories above antar/panel/server.py."""
    return Path(__file__).resolve().parents[2]


class PanelError(RuntimeError):
    """Something the operator asked for could not be done, in plain words."""


def make_handler(config, registry: jobs.Registry):
    assets = config.path("paths.assets")

    class Handler(BaseHTTPRequestHandler):
        server_version = "PSYCHE"
        protocol_version = "HTTP/1.1"

        # ------------------------------------------------------- plumbing
        def log_message(self, *args) -> None:
            """Silence the one-line-per-request default: the console is the job's."""

        def _send(self, status: int, body: bytes, content_type: str,
                  extra: dict | None = None) -> None:
            # The browser may leave while a long job (the live key test can
            # take a couple of minutes) is still running. On Windows that
            # surfaces as ConnectionAbortedError [WinError 10053], on Linux
            # as BrokenPipeError. They are all ConnectionError - the client
            # is gone, so there is nobody to send (or report) to. Swallow it
            # instead of printing a traceback that looks like a real crash.
            try:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                for key, value in (extra or {}).items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(body)
            except (ConnectionError, OSError):
                # BrokenPipe / ConnectionReset / ConnectionAborted (Win 10053)
                pass

        def _json(self, payload, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        def _error(self, message: str, status: int = 400) -> None:
            self._json({"error": message}, status)

        def _body(self) -> dict:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return {}
            if not length:
                return {}
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise PanelError("the panel sent a request that was not JSON")

        # ----------------------------------------------------------- GET
        def do_GET(self) -> None:               # noqa: N802
            parsed = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            path = parsed.path.rstrip("/") or "/"
            try:
                if path in ("/", "/index.html"):
                    return self._send(200, PAGE.encode("utf-8"),
                                      "text/html; charset=utf-8")
                if path.startswith("/assets/"):
                    return self._asset(path[len("/assets/"):])
                if path == "/api/state":
                    return self._json(self._state())
                if path == "/api/keys/health":
                    return self._json(self._keys_health({}))
                if path == "/api/keys/quarantine":
                    return self._json(self._keys_quarantine({}))
                if path == "/api/keys/vendor-url":
                    return self._json(self._keys_vendor_url({}))
                if path.startswith("/api/tab/"):
                    return self._json(self._tab(path[len("/api/tab/"):].lower(),
                                                query.get("render", "")))
                if path.startswith("/api/job/"):
                    return self._json(self._job(path[len("/api/job/"):],
                                                int(query.get("since", 0) or 0)))
                if path == "/media/video":
                    return self._media_video(query.get("render", ""))
                if path == "/media/thumbnail":
                    return self._media_thumbnail(query.get("render", ""))
                if path == "/media/real_thumbnail":
                    return self._media_real_thumbnail(query.get("render", ""))
                return self._error(f"nothing is served at {path}", 404)
            except PanelError as exc:
                return self._error(str(exc), 400)
            except ConnectionError:
                return
            except Exception as exc:                    # never a bare 500
                log.fail(f"panel: {type(exc).__name__}: {exc}")
                return self._error(f"{type(exc).__name__}: {exc}", 500)

        def _asset(self, name: str):
            """
            A file under assets/ and nowhere else.

            Sub-folders are allowed (the font lives in assets/fonts/), but the
            resolved path has to stay inside assets/ - a request for
            /assets/../.env is answered with 404, not with a key file.
            """
            name = name.replace("\\", "/").lstrip("/")
            root = Path(assets).resolve()
            path = (root / name).resolve()
            if not name or root not in path.parents or not path.is_file():
                return self._error(f"no such asset: {name}", 404)
            kind = MIME.guess_type(str(path))[0] or "application/octet-stream"
            return self._send(200, path.read_bytes(), kind)

        # ---------------------------------------------------------- POST
        def do_POST(self) -> None:              # noqa: N802
            parsed = urlparse(self.path)
            try:
                body = self._body()
                route = parsed.path.rstrip("/")
                if route == "/api/run":
                    return self._json(self._run(body))
                if route == "/api/score":
                    return self._json(data.rescore(
                        config, body.get("render_id") or data.current_render(config),
                        body.get("title", "")))
                if route == "/api/save":
                    return self._json(self._save(body))
                if route == "/api/thumbnail":
                    return self._json(thumbs.manual(
                        config, body.get("render_id") or data.current_render(config),
                        float(body.get("second", 0))))
                if route == "/api/learn/import":
                    source = body.get("source", "")
                    return self._json(data.import_analytics_csv(config, source))
                if route == "/api/learn/run":
                    return self._json(data.run_learn(config))
                if route == "/api/keys/add":
                    return self._json(self._keys_add(body))
                if route == "/api/keys/test":
                    return self._json(self._keys_test(body))
                if route == "/api/keys/sync":
                    return self._json(self._keys_sync(body))
                if route == "/api/keys/health":
                    return self._json(self._keys_health(body))
                if route == "/api/keys/quarantine":
                    return self._json(self._keys_quarantine(body))
                if route == "/api/keys/vendor-url":
                    return self._json(self._keys_vendor_url(body))
                return self._error(f"nothing is posted to {route}", 404)
            except jobs.Refused as exc:
                return self._error(str(exc), 409)
            except (thumbs.ThumbError, PanelError) as exc:
                return self._error(str(exc), 400)
            except ConnectionError:
                # client navigated away mid-request (Win 10053 / broken pipe);
                # nothing to send back and nothing real went wrong
                return
            except Exception as exc:
                log.fail(f"panel: {type(exc).__name__}: {exc}")
                return self._error(f"{type(exc).__name__}: {exc}", 500)

        # ------------------------------------------------------- handlers
        def _state(self) -> dict:
            """The header's numbers, read from the files the stages wrote."""
            render_id = data.current_render(config)
            details = data.details(config, render_id) if render_id else {}
            checked = data.check(config, render_id) if render_id else {}
            job = registry.current()
            last = registry.recent(1)
            return {
                "render_id": render_id,
                "score": (checked.get("scorecard") or {}).get("total"),
                "title_score": details.get("chosen_score") if details.get("ready") else None,
                "video_on_disk": bool(data.video_path(config, render_id)) if render_id else False,
                "running": bool(job),
                "job_id": job.id if job else (last[0].id if last else ""),
                "job_title": job.title if job else "",
                "busy_message": registry.busy_message(),
                "version": VERSION,
            }

        def _tab(self, name: str, render_id: str) -> dict:
            table = {
                "studio": data.home, "home": data.home,
                "writer": data.writer, "picture": data.picture,
                "check": data.check, "details": data.details, "score": data.score,
                "proofs": data.proof, "proof": data.proof,
                "keys": lambda cfg, rid="": data.keys(cfg),
                "learn": data.learn,
                "settings": lambda cfg, rid="": data.settings(cfg),
            }
            if name not in table:
                raise PanelError(f"no such tab: {name}")
            return table[name](config, render_id)

        def _job(self, job_id: str, since: int) -> dict:
            job = registry.get(job_id)
            if not job:
                raise PanelError(f"no job called {job_id} - it may have been cleared")
            return job.as_dict(since=since)

        def _run(self, body: dict) -> dict:
            what = (body.get("what") or "").strip()
            render_id = body.get("render_id") or data.current_render(config)
            refresh = bool(body.get("refresh"))
            offline = bool(body.get("offline"))
            if what == "video":
                job = registry.start("make one video", "topics -> write -> voice -> "
                                     "picture -> build -> check -> details",
                                     jobs.make_one_video(config))
                return {"id": job.id, "what": what, "state": job.state}
            if what == "topics":
                title = "choose topics (offline)" if offline else "choose topics"
                job = registry.start(title, "generate and test Hindi topics",
                                     jobs.run_topics(config, offline=offline))
                return {"id": job.id, "what": what, "state": job.state}
            if what == "write":
                title = "write the script (offline)" if offline else "write the script"
                job = registry.start(title, "write a Hindi script from the chosen topic",
                                     jobs.run_write(config, offline=offline))
                return {"id": job.id, "what": what, "state": job.state}
            if what == "voice":
                job = registry.start("record the voice", "turn the script into audio",
                                     jobs.run_voice(config, render_id),
                                     render_id=render_id)
                return {"id": job.id, "what": what, "state": job.state}
            if what == "picture":
                job = registry.start("find the picture", "build the shot plan",
                                     jobs.run_picture(config, render_id),
                                     render_id=render_id)
                return {"id": job.id, "what": what, "state": job.state}
            if what == "build":
                job = registry.start("render the video", "assemble clips, grade, burn text",
                                     jobs.run_build(config))
                return {"id": job.id, "what": what, "state": job.state}
            if what == "check":
                job = registry.start("check the video", "the full check suite",
                                     jobs.run_check(config, render_id),
                                     render_id=render_id)
                return {"id": job.id, "what": what, "state": job.state}
            if what == "details":
                job = registry.start("write the details",
                                     "harvest, candidates, description, tags, pinned "
                                     "comment" + (" (live search again)" if refresh else ""),
                                     jobs.run_details(config, render_id, refresh),
                                     render_id=render_id)
                return {"id": job.id, "what": what, "state": job.state}
            if what == "proof":
                job = registry.start("proof stage", "cut thumbnails + run every proof",
                                     jobs.run_proof(config, render_id),
                                     render_id=render_id)
                return {"id": job.id, "what": what, "state": job.state}
            if what == "learn":
                job = registry.start("learn stage", "analytics -> next topic brief",
                                     jobs.run_learn(config))
                return {"id": job.id, "what": what, "state": job.state}
            if what == "keys":
                job = registry.start("test the keys",
                                     "every key, every route, live",
                                     jobs.run_keys(config))
                return {"id": job.id, "what": what, "state": job.state}
            raise PanelError(f"there is no job called '{what}'")

        def _save(self, body: dict) -> dict:
            from ..details import assemble, write as write_details

            render_id = body.get("render_id") or data.current_render(config)
            path = config.path("paths.output") / "details" / f"{render_id}_details.json"
            payload = data._read(path)
            if not payload:
                raise PanelError(f"there are no details on disk for {render_id} - "
                                 f"run the details stage first")

            title = (body.get("title_hi") or "").strip()
            if title:
                # the panel does not get to declare a score: it re-scores the
                # title the operator typed, on this render's own phrase list
                rescored = data.rescore(config, render_id, title)
                payload["title_hi"] = title
                payload["chosen_score"] = rescored["total"]
                payload["chosen_parts"] = rescored["parts"]
            if body.get("description") is not None:
                payload["description"] = body["description"]
            if body.get("tags") is not None:
                payload["tags"] = [t for t in body["tags"] if str(t).strip()]
            if body.get("pinned_comment") is not None:
                payload["pinned_comment"] = body["pinned_comment"]

            # the hashtags live in the description, so they are read back out of it
            payload["hashtags"] = re.findall(r"#[^\s#]+", payload.get("description", ""))

            payload["edited_by_hand"] = True
            payload["edited_at"] = time.time()
            payload["audit"] = assemble.audit(payload)
            write_details(config, render_id, payload)
            failures = [row for row in payload["audit"] if not row["pass"]]
            return {
                "saved": str(path),
                "title_score": payload["chosen_score"],
                "audit": payload["audit"],
                "failed": len(failures),
                "note": ("saved, and every details rule passes" if not failures else
                         "saved, but the rules above do not all pass - the check "
                         "stage will report the same failures"),
            }

        # ----------------------------------------------------------- keys
        def _keys_add(self, body: dict) -> dict:
            """Add one key, then test it against the live API."""
            from .. import envfile
            from ..keys import KeyRing
            service = (body.get("service") or "").strip().lower()
            value = (body.get("value") or "").strip()
            if not service or not value:
                raise PanelError("need both service and value")
            ring = KeyRing(config.path("paths.state") / "keys.json",
                           max_keys=int(config.get("keys.max_keys", 50)),
                           never_delete=bool(config.get("keys.never_delete_dead", True)))
            key = ring.add(service, value)
            # run the side-effect import from .env too, so the ring reflects the file
            envfile.load(_root(), ring, quiet=True)
            return {"added": key.masked, "service": service}

        def _keys_test(self, body: dict) -> dict:
            """Re-test every key (or one service) against the live API."""
            from ..cli import cmd_keys_test as run_keys_test
            service = body.get("service") or ""
            args = ["--all"] if body.get("all") else ([service] if service else [])
            try:
                run_keys_test(config, args)
            except Exception as exc:
                raise PanelError(f"key test stopped: {exc}") from exc
            # re-read keys for the rail
            return {"ran": True, "keys": data.keys(config)}

        def _keys_sync(self, body: dict) -> dict:
            """Import any keys sitting in .env into keys.json, then test them."""
            from .. import envfile
            from ..keys import KeyRing
            ring = KeyRing(config.path("paths.state") / "keys.json",
                           max_keys=int(config.get("keys.max_keys", 50)),
                           never_delete=bool(config.get("keys.never_delete_dead", True)))
            summary = envfile.load(_root(), ring, quiet=True)
            note = f"added {summary.get('added', 0)}, already on file {summary.get('already_on_file', 0)}"
            return summary if isinstance(summary, dict) else {"added": 0, "note": str(summary)}

        def _keys_health(self, body: dict) -> dict:
            """Group keys by AI service so the refresh button knows what's dead."""
            from ..keys import KeyRing
            ring = KeyRing(config.path("paths.state") / "keys.json",
                           max_keys=int(config.get("keys.max_keys", 50)),
                           never_delete=bool(config.get("keys.never_delete_dead", True)))
            ai_services = ("groq", "gemini", "openai", "anthropic",
                           "openrouter", "together", "huggingface")
            grouped: dict[str, list] = {s: [] for s in ai_services}
            for key in ring.all():
                if key.service in grouped:
                    grouped[key.service].append({
                        "masked": key.masked,
                        "state": key.state,
                        "reason": key.reason,
                    })
            return grouped

        # ---------------------------------------------------------- media
        def _keys_vendor_url(self, body: dict) -> dict:
            """
            Map each LLM vendor to its API-key console URL.

            The panel uses this to open the right vendor's site when the
            user clicks Refresh AI key, instead of always opening Groq
            (which is what the old code did - silently wrong when the
            user's dead key was actually Anthropic or OpenAI).
            """
            return {
                "vendors": [
                    {"service": "groq",       "name": "Groq",       "url": "https://console.groq.com/keys",      "free": True},
                    {"service": "gemini",     "name": "Gemini",     "url": "https://aistudio.google.com/apikey", "free": True},
                    {"service": "openai",     "name": "OpenAI",     "url": "https://platform.openai.com/api-keys", "free": False},
                    {"service": "anthropic",  "name": "Anthropic",  "url": "https://console.anthropic.com/settings/keys", "free": False},
                    {"service": "openrouter", "name": "OpenRouter", "url": "https://openrouter.ai/settings/keys", "free": True},
                    {"service": "huggingface","name": "Huggingface","url": "https://huggingface.co/settings/tokens", "free": True},
                    {"service": "together",   "name": "Together",   "url": "https://api.together.ai/settings/api-keys", "free": True},
                    {"service": "elevenlabs", "name": "ElevenLabs", "url": "https://elevenlabs.io/app/settings/api-keys", "free": False},
                ],
            }

        def _keys_quarantine(self, body: dict) -> dict:
            """
            Show every dead key on disk. PSYCHE moves dead keys out of the
            active ring into keys_dead.json so the active ring is small
            and clean; this endpoint reads the quarantine file.
            """
            from pathlib import Path
            import json as _json
            dead_path = config.path("paths.state") / "keys_dead.json"
            if not dead_path.exists():
                return {"count": 0, "keys": [], "path": str(dead_path),
                        "note": "no dead keys yet - every key on file is alive or unknown"}
            try:
                raw = _json.loads(dead_path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, _json.JSONDecodeError):
                return {"count": 0, "keys": [], "path": str(dead_path),
                        "note": "keys_dead.json is unreadable"}
            archive = raw.get("keys", []) if isinstance(raw, dict) else raw
            return {
                "count": len(archive),
                "path": str(dead_path),
                "keys": [{"masked": k.get("masked", ""),
                          "service": k.get("service", ""),
                          "reason": k.get("reason", ""),
                          "died_at": k.get("died_at", 0),
                          "uses": k.get("uses", 0),
                          "fails": k.get("fails", 0)}
                         for k in archive],
            }

        def _media_video(self, render_id: str):
            render_id = render_id or data.current_render(config)
            path = data.video_path(config, render_id)
            if not path:
                raise PanelError(
                    f"{render_id}.mp4 is not in output/video. Videos are delivered "
                    f"in PSYCHE_VIDEOS.zip and deleted from the workshop, so there is "
                    f"nothing to play here until one is present.")
            return self._ranged(path, "video/mp4")

        def _media_thumbnail(self, render_id: str):
            render_id = render_id or data.current_render(config)
            path = data.thumbnail_path(config, render_id)
            if not path:
                raise PanelError("no thumbnail has been picked or cut yet")
            return self._send(200, Path(path).read_bytes(), "image/jpeg")

        def _media_real_thumbnail(self, render_id: str):
            """
            The proof stage's landscape thumbnail - 1280x720, with the title
            over the footage. Served for the DETAILS tab.

            Falls back to the manual pick if the proof stage has not run yet,
            so a page reload after a details save does not show a missing
            image - it shows the best thumbnail the workshop has.
            """
            render_id = render_id or data.current_render(config)
            details = data.details(config, render_id)
            record = details.get("thumbnail_record") or {}
            landscape = record.get("landscape") or details.get("thumbnail_landscape")
            if landscape and Path(landscape).exists():
                return self._send(200, Path(landscape).read_bytes(), "image/jpeg")
            full = record.get("full") or details.get("thumbnail_path")
            if full and Path(full).exists():
                return self._send(200, Path(full).read_bytes(), "image/jpeg")
            raise PanelError("no real thumbnail on disk yet - run: python run.py proof")

        def _ranged(self, path: Path, content_type: str):
            """Serve a file with byte ranges - the video scrubber needs them."""
            size = path.stat().st_size
            header = self.headers.get("Range") or ""
            match = re.match(r"bytes=(\d*)-(\d*)", header)
            if not match:
                return self._send(200, path.read_bytes(), content_type,
                                  {"Accept-Ranges": "bytes"})
            start = int(match.group(1) or 0)
            end = int(match.group(2) or size - 1)
            end = min(end, size - 1)
            if start > end:
                return self._error("that byte range does not exist", 416)
            with path.open("rb") as handle:
                handle.seek(start)
                chunk = handle.read(end - start + 1)
            self.send_response(206)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(chunk)))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            try:
                self.end_headers()
                self.wfile.write(chunk)
            except (ConnectionError, OSError):
                pass

    return Handler


def start(config, host: str = "0.0.0.0", port: int = 8787, *,
          quiet: bool = False, tries: int = 6):
    """
    Bind the panel and start serving in a background thread.

    Returns (server, registry, url). The caller decides whether to block on it.
    Port 0 asks the operating system for a free port - that is what the tests
    use, so a test never collides with a panel the operator left open.
    """
    registry = jobs.Registry(config)
    handler = make_handler(config, registry)

    server = None
    wanted = port
    for _ in range(tries):
        try:
            server = ThreadingHTTPServer((host, wanted), handler)
            break
        except OSError as exc:
            if port == 0:
                raise
            log.warn(f"port {wanted} is busy ({exc}) - trying {wanted + 1}")
            wanted += 1
    if server is None:
        raise PanelError(f"no free port between {port} and {port + tries}")

    server.daemon_threads = True
    shown = "localhost" if host in ("0.0.0.0", "") else host
    url = f"http://{shown}:{server.server_port}/"
    if not quiet:
        log.ok(f"the panel is running at {url}")
        log.info("everything it shows comes out of output/ and config/ - it "
                 "invents nothing")
    thread = threading.Thread(target=server.serve_forever,
                              kwargs={"poll_interval": 0.4},
                              name="antar-panel", daemon=True)
    thread.start()
    return server, registry, url


def serve(config, host: str = "0.0.0.0", port: int = 8787, *, quiet: bool = False) -> int:
    """Run the panel in the foreground until Ctrl-C."""
    server, _, url = start(config, host, port, quiet=quiet)
    if not quiet:
        log.info("open that address, or stop the panel with Ctrl-C")
        print(f"PANEL_URL={url}", flush=True)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        log.warn("panel stopped by the operator")
    finally:
        server.shutdown()
        server.server_close()
    return 0
