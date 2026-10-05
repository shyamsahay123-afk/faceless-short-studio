"""
ANTAR panel - the jobs.

One job at a time. That is not a limitation of the code, it is the rule the
whole project runs on: the pipeline stages write to the same folders, and two
of them running together is how a half-built video ends up beside a finished
one. A second request while a job is running is refused in plain words, and the
refusal names the job that is already running.

Every job's output is captured live through the log sink, so the browser shows
the console exactly as it happens, line for line, marker for marker. Nothing is
summarised, nothing is invented: if a stage fails, the job ends in `failed`
with the stage's own error text and the last lines of its own output.
"""

from __future__ import annotations

import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from .. import log

MAX_LINES = 600


@dataclass
class Job:
    id: str
    title: str
    what: str
    state: str = "running"          # running | done | failed
    created: float = field(default_factory=time.time)
    started: float = 0.0
    ended: float = 0.0
    exit_code: int | None = None
    error: str = ""
    lines: list[str] = field(default_factory=list)
    result: dict = field(default_factory=dict)
    render_id: str = ""

    def as_dict(self, since: int = 0) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "what": self.what,
            "state": self.state,
            "render_id": self.render_id,
            "seconds": round((self.ended or time.time()) - (self.started or self.created), 1),
            "exit_code": self.exit_code,
            "error": self.error,
            "result": self.result,
            "lines_total": len(self.lines),
            "lines": self.lines[since:],
            "since": len(self.lines),
        }


class Refused(Exception):
    """A job was asked for while another one was running."""


class Registry:
    """
    The run queue: one job at a time, its output kept for the browser.
    """

    def __init__(self, config, keep: int = 12):
        self.config = config
        self.keep = keep
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()
        self._counter = 0

    # ------------------------------------------------------------------ read
    def current(self) -> Job | None:
        for job_id in reversed(self._order):
            job = self._jobs[job_id]
            if job.state == "running":
                return job
        return None

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def recent(self, limit: int = 6) -> list[Job]:
        return [self._jobs[i] for i in reversed(self._order[-limit:])]

    def busy_message(self) -> str:
        job = self.current()
        if not job:
            return ""
        return (f"'{job.title}' is still running ({round(time.time() - job.started)}s in). "
                f"ANTAR runs one job at a time - wait for it, or read its output below.")

    # ----------------------------------------------------------------- write
    def start(self, title: str, what: str, fn, *, render_id: str = "") -> Job:
        with self._lock:
            running = self.current()
            if running:
                raise Refused(self.busy_message())
            self._counter += 1
            job = Job(id=f"job{self._counter:04d}", title=title, what=what,
                      render_id=render_id)
            self._jobs[job.id] = job
            self._order.append(job.id)
            while len(self._order) > self.keep:
                old = self._order.pop(0)
                self._jobs.pop(old, None)

        thread = threading.Thread(target=self._run, args=(job, fn),
                                  name=f"antar-{job.id}", daemon=True)
        thread.start()
        return job

    def _run(self, job: Job, fn) -> None:
        job.started = time.time()

        def sink(marker: str, message: str, line: str) -> None:
            with self._lock:
                job.lines.append(line)
                if len(job.lines) > MAX_LINES:
                    del job.lines[:len(job.lines) - MAX_LINES]

        log.add_sink(sink)
        log.banner(f"ANTAR - {job.title}", job.render_id or "panel")
        if job.what:
            log.info(f"asked to: {job.what}")
        try:
            result = fn(job)
            job.exit_code = int(result) if isinstance(result, int) else 0
            if job.exit_code != 0:
                job.state = "failed"
                job.error = (f"the stage stopped with code {job.exit_code} - "
                             f"the reason is in the output above")
        except Exception as exc:
            job.state = "failed"
            job.error = f"{type(exc).__name__}: {exc}"
            log.fail(job.error)
            for line in traceback.format_exc().strip().splitlines()[-4:]:
                log.info("   " + line)
        else:
            if job.state == "running":
                job.state = "done"
        finally:
            log.remove_sink(sink)
            job.ended = time.time()
            if job.state == "running":
                job.state = "done"
            log.rule()
            mark = log.ok if job.state == "done" else log.fail
            mark(f"{job.title}: {job.state} in {job.ended - job.started:.1f}s")


# --------------------------------------------------------------- the stages


def newest_script_index(config) -> int:
    """Where the newest script sits in the list the stage commands read."""
    files = sorted((config.path("paths.output") / "scripts").glob("*.json"))
    return max(0, len(files) - 1)


def newest_render_id(config) -> str:
    videos = sorted(p for p in (config.path("paths.output") / "video").glob("*.mp4")
                    if not p.stem.upper().startswith("TEST"))
    if videos:
        return videos[-1].stem
    builds = sorted(p for p in (config.path("paths.output") / "video").glob("*_build.json")
                    if not p.name.upper().startswith("TEST"))
    return builds[-1].name[: -len("_build.json")] if builds else ""


def _stage(log_fn, name: str):
    """
    A decorator that names each stage inside the job's own output, so the
    console the user reads is the console the command line would print.
    """
    def wrap(fn):
        def run(*args, **kwargs):
            log_fn(f">> {name}")
            return fn(*args, **kwargs)
        run.__name__ = fn.__name__
        return run
    return wrap


def make_one_video(config):
    """
    The whole pipeline, in order, the way the command line runs it:

        topics -> write -> voice -> picture -> build -> check -> details

    Every stage is the same function the command line calls, so the panel can
    never drift from the tool. The first stage that fails ends the job with its
    own error text; nothing downstream is attempted on a missing input.
    """
    from .. import cli

    def run(job: Job) -> int:
        # Try online first, fall back to offline pool if no LLM keys alive.
        # This makes "Make one video" work even when every AI key is dead,
        # using hand-verified topics and template - better than a silent fail.
        log.step("choose topics")
        code = cli.cmd_topics(config, [])
        if code not in (0, 1):
            log.warn("online topics failed - trying offline pool")
            code = cli.cmd_topics(config, ["--offline"])
            if code not in (0, 1):
                log.fail(f"choose topics stopped the run (code {code})")
                return code
            log.ok("offline topics succeeded")
        elif code == 1:
            log.warn("choose topics finished with warnings")

        log.step("write the script")
        code = cli.cmd_write(config, [])
        if code not in (0, 1):
            log.warn("online write failed - trying offline template")
            code = cli.cmd_write(config, ["--offline"])
            if code not in (0, 1):
                log.fail(f"write the script stopped the run (code {code})")
                return code
            log.ok("offline write succeeded")
        elif code == 1:
            log.warn("write the script finished with warnings")

        index = newest_script_index(config)
        steps = (
            ("record the voice", lambda: cli.cmd_voice(config, [str(index)])),
            ("find the picture", lambda: cli.cmd_picture(config, [str(index)])),
            ("render the video", lambda: cli.cmd_build(config, [])),
        )
        for name, call in steps:
            log.step(f"{name}")
            code = call()
            if code not in (0, 1):
                log.fail(f"{name} stopped the run (code {code})")
                return code
            if code == 1:
                log.warn(f"{name} finished with warnings")

        render_id = newest_render_id(config)
        job.render_id = render_id
        for name, call in (("check the result", lambda: cli.cmd_check(config, [render_id] or [])),
                           ("write the details", lambda: cli.cmd_details(config, [render_id] or []))):
            log.step(f"{name}")
            code = call()
            if code not in (0, 1):
                log.fail(f"{name} stopped the run (code {code})")
                return code

        job.result = {"render_id": render_id}
        log.ok(f"one video, finished: {render_id}")
        return 0

    return run


def run_topics(config, offline: bool = False):
    from .. import cli
    args = ["--offline"] if offline else []
    return lambda job: cli.cmd_topics(config, args)


def run_write(config, offline: bool = False):
    from .. import cli
    args = ["--offline"] if offline else []
    return lambda job: cli.cmd_write(config, args)


def run_voice(config, render_id: str = ""):
    from .. import cli
    idx = ""
    if render_id:
        # voice stage reads by script index; if render_id given, find its index
        try:
            from pathlib import Path
            import json
            scripts_dir = config.path("paths.output") / "scripts"
            files = sorted(scripts_dir.glob("*.json"))
            for i, p in enumerate(files):
                try:
                    if json.loads(p.read_text(encoding="utf-8")).get("render_id") == render_id:
                        idx = str(i)
                        break
                except Exception:
                    continue
        except Exception:
            idx = ""
    args = [idx] if idx else []
    return lambda job: cli.cmd_voice(config, args)


def run_picture(config, render_id: str = ""):
    from .. import cli
    idx = ""
    if render_id:
        try:
            from pathlib import Path
            import json
            scripts_dir = config.path("paths.output") / "scripts"
            files = sorted(scripts_dir.glob("*.json"))
            for i, p in enumerate(files):
                try:
                    if json.loads(p.read_text(encoding="utf-8")).get("render_id") == render_id:
                        idx = str(i)
                        break
                except Exception:
                    continue
        except Exception:
            idx = ""
    args = [idx] if idx else []
    return lambda job: cli.cmd_picture(config, args)


def run_build(config):
    from .. import cli
    return lambda job: cli.cmd_build(config, [])


def run_check(config, render_id: str = ""):
    from .. import cli
    return lambda job: cli.cmd_check(config, [render_id] if render_id else [])


def run_details(config, render_id: str = "", refresh: bool = False):
    from .. import cli
    args = [render_id] if render_id else []
    if refresh:
        args.append("--refresh")
    return lambda job: cli.cmd_details(config, args)


def run_proof(config, render_id: str = ""):
    from .. import cli
    return lambda job: cli.cmd_proof(config, [render_id] if render_id else [])


def run_learn(config):
    from .. import cli
    return lambda job: cli.cmd_learn(config, [])


def run_keys(config):
    from .. import cli
    return lambda job: cli.cmd_keys_test(config, ["--all"])
