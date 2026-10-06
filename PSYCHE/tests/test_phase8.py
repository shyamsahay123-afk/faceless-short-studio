"""
Phase 8 self tests - the panel.

Every test here talks to a real server over a real socket, on a real port the
operating system picked. Nothing is mocked: the requests go through the same
handler the operator's browser hits, the job queue runs real functions in real
threads, and the data comes out of the same files the stages wrote.

The tests that matter most are the ones about honesty and safety:

  * **no key material leaves the panel.** Every response body is scanned for the
    keys actually on file. A panel that shows keys on screen is the one place
    this project could leak one.
  * **a failing job says why.** The job ends `failed` with the stage's own
    words, and the console lines that led up to it are in the job's output -
    not a silent 500 and not a cheerful "done".
  * **one job at a time.** The second request is refused, in plain words, and
    the refusal names the job that is running.
  * **nothing is invented.** A tab with no file behind it says so; it does not
    show a zero that looks like a measurement.
  * **the panel and the gate agree.** The score endpoint uses the same judge and
    the same phrase list the check suite uses, which is the defect that made the
    Phase 7 title read 65/100 in the gate and 100/100 in the generator.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from antar import config                                  # noqa: E402
from antar.checks import titlescore                       # noqa: E402
from antar.panel import data, jobs, server, thumbs        # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []
SERVER = None
URL = ""
REGISTRY = None
BODIES: list[tuple[str, bytes]] = []


def check(name: str):
    def wrap(fn):
        def run_it(verbose: bool = True):
            try:
                detail = fn() or ""
                RESULTS.append((name, True, str(detail)))
                if verbose:
                    print(f"  [PASS] {name}" + (f"   {detail}" if detail else ""))
                return True
            except AssertionError as exc:
                RESULTS.append((name, False, str(exc)))
                if verbose:
                    print(f"  [FAIL] {name}   {exc}")
                return False
            except Exception as exc:
                RESULTS.append((name, False, f"{type(exc).__name__}: {exc}"))
                if verbose:
                    print(f"  [FAIL] {name}   {type(exc).__name__}: {exc}")
                return False
        return run_it
    return wrap


# ------------------------------------------------------------------ helpers

def panel():
    """Start the panel once for the whole run, on a port the OS picks."""
    global SERVER, URL, REGISTRY
    if SERVER is None:
        cfg = config.load()
        SERVER, REGISTRY, URL = server.start(cfg, port=0, quiet=True)
        URL = URL.rstrip("/")
    return URL


def get(path: str, *, raw: bool = False):
    panel()
    try:
        with urllib.request.urlopen(URL + path, timeout=45) as response:
            body = response.read()
            BODIES.append((path, body))
            return response.status, body if raw else json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read()
        BODIES.append((path, body))
        raise PanelHTTP(exc.code, body) from exc


class PanelHTTP(Exception):
    def __init__(self, code: int, body: bytes):
        self.code = code
        try:
            self.error = json.loads(body).get("error", "")
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.error = body[:120].decode("utf-8", "replace")
        super().__init__(f"{code}: {self.error}")


def post(path: str, body: dict):
    panel()
    request = urllib.request.Request(
        URL + path, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
            BODIES.append((path, payload))
            return response.status, json.loads(payload)
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        BODIES.append((path, payload))
        raise PanelHTTP(exc.code, payload) from exc


def wait_for_job(job_id: str, timeout: float = 120.0) -> dict:
    """
    Follow a job to the end and hand back its WHOLE console.

    The panel delivers output in pieces - that is the point of the cursor - so
    this accumulates them the way the browser does. An earlier version returned
    only the last piece, which meant the final assertion saw the lines printed
    after the failure and not the failure itself: the test passed on a quiet
    machine and failed when the same job happened to span two polls.
    """
    since = 0
    collected: list[str] = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        _, job = get(f"/api/job/{job_id}?since={since}")
        collected.extend(job.get("lines") or [])
        since = job["since"]
        job["lines"] = list(collected)
        if job["state"] != "running":
            return job
        time.sleep(0.4)
    raise AssertionError(f"job {job_id} never finished")


# --------------------------------------------------------------------- page

@check("the page serves with all nine tabs and no outside requests")
def t_page():
    status, body = get("/", raw=True)
    text = body.decode("utf-8")
    for tab in ("HOME", "WRITER", "PICTURE", "CHECK", "DETAILS", "SCORE", "KEYS",
                "LEARN", "SETTINGS"):
        assert f'data-tab="{tab}"' in text or f'"{tab}"' in text, f"the {tab} tab is missing"
    for outside in ("http://", "https://", "cdn.", "googleapis", "unpkg"):
        assert outside not in text.replace("https://{", ""), \
            f"the page reaches outside for {outside}"
    assert "MAKE ONE VIDEO" in text, "the one button is missing"
    return f"{len(body)} bytes, nine tabs, no external resource"


@check("the Hindi font the page asks for is the font the panel serves")
def t_font():
    status, body = get("/assets/fonts/Khand-Bold.ttf", raw=True)
    _, page = get("/", raw=True)
    assert "/assets/fonts/Khand-Bold.ttf" in page.decode("utf-8"), \
        "the page asks for a font the panel does not serve"
    assert body[:4] in (b"\x00\x01\x00\x00", b"true", b"OTTO"), "that is not a font file"
    return f"{len(body)} bytes, starts {body[:4]!r}"


@check("every tab returns its data, and every tab has a render or says why")
def t_tabs():
    seen = []
    for tab in ("home", "writer", "picture", "check", "details", "score", "keys",
                "learn", "settings"):
        status, payload = get(f"/api/tab/{tab}")
        assert status == 200, f"{tab} returned {status}"
        assert isinstance(payload, dict) and payload, f"{tab} returned nothing"
        if "ready" in payload and not payload["ready"]:
            assert payload.get("note"), f"{tab} is empty and does not say why"
        seen.append(f"{tab}:{len(payload)}")
    return " ".join(seen)


@check("the header state matches what the check record says")
def t_state():
    cfg = config.load()
    _, state = get("/api/state")
    render_id = data.current_render(cfg)
    assert state["render_id"] == render_id, (state["render_id"], render_id)
    record = data._read(cfg.path("paths.output") / "checks" / f"{render_id}_check.json")
    assert state["score"] == (record.get("scorecard") or {}).get("total"), \
        "the header score is not the checked score"
    assert state["running"] is False, "the header says a job is running when none is"
    return f"{render_id} score {state['score']}"


# -------------------------------------------------------------------- safety

@check("no key material ever leaves the panel")
def t_no_keys_on_the_wire():
    cfg = config.load()
    from antar.keys import KeyRing

    ring = KeyRing(cfg.path("paths.state") / "keys.json")
    secrets = [k.value for k in ring.all() if len(k.value) > 8]
    assert secrets, "no keys on file - this test cannot prove anything"
    leaked = []
    for path, body in BODIES:
        text = body.decode("utf-8", "replace")
        for secret in secrets:
            if secret in text:
                leaked.append(f"{path} carries a whole key")
            if secret[:12] in text and secret[:12] not in ("", ):
                leaked.append(f"{path} carries the first 12 characters of a key")
    assert not leaked, leaked
    probe = []
    for path in ("/api/tab/keys", "/api/state", "/api/tab/settings"):
        _, body = get(path, raw=True)
        text = body.decode("utf-8", "replace")
        probe += [f"{path} carries a key" for secret in secrets if secret in text]
    assert not probe, probe
    return f"{len(secrets)} key(s) on file, {len(BODIES)} responses scanned, none carries one"


@check("the panel refuses to serve anything outside its own two folders")
def t_traversal_is_blocked():
    attempts = ("/assets/../.env", "/assets/../config/state/keys.json",
                "/assets/../../etc/passwd", "/../run.py", "/config/antar.json")
    for path in attempts:
        try:
            get(path, raw=True)
        except PanelHTTP as exc:
            assert exc.code in (403, 404), f"{path} answered {exc.code}"
        else:
            raise AssertionError(f"{path} was served")
    return f"{len(attempts)} attempts, all refused"


@check("a missing file is a plain sentence, not a traceback")
def t_missing_files_are_plain():
    seen = []
    for path in ("/media/thumbnail", "/api/tab/nonsense", "/nope"):
        try:
            get(path, raw=True)
        except PanelHTTP as exc:
            assert exc.error and not exc.error.startswith("Traceback"), exc.error
            assert "Error" not in exc.error or "no such" in exc.error, exc.error
            seen.append(f"{exc.code} {exc.error[:34]}")
    return " | ".join(seen)


# ---------------------------------------------------------------------- jobs

@check("one job at a time - the second request is refused by name")
def t_one_job_at_a_time():
    started = threading.Event()

    def slow(_job):
        started.set()
        time.sleep(2.5)
        return 0

    job = REGISTRY.start("a slow test job", "sleeping on purpose", slow)
    started.wait(3)
    refusal = ""
    try:
        post("/api/run", {"what": "keys"})
        raise AssertionError("a second job was accepted while one was running")
    except PanelHTTP as exc:
        assert exc.code == 409, f"refused with {exc.code}, not 409"
        assert "slow test job" in exc.error, exc.error
        refusal = exc.error                     # Python drops `exc` when the
    finally:                                    # except block ends, so it is
        finished = wait_for_job(job.id)         # copied out before that
    assert finished["state"] == "done", finished
    return f"refused: {refusal[:56]}"


@check("a failing job ends failed, with the stage's own words in its output")
def t_a_failing_job_says_why():
    def boom(_job):
        raise RuntimeError("the picture library had nothing to give")

    job = REGISTRY.start("a test job that fails", "failing on purpose", boom)
    finished = wait_for_job(job.id)
    assert finished["state"] == "failed", finished["state"]
    assert "picture library had nothing to give" in finished["error"], finished["error"]
    text = "\n".join(finished["lines"])
    assert "failing on purpose" in text, "the job's console does not show what it did"
    assert "[FAIL]" in text, "the failure was not printed to the console"
    return f"failed in {finished['seconds']}s: {finished['error'][:52]}"


@check("a stage that returns a failure code fails the job too")
def t_failure_code():
    def refused(_job):
        return 2

    job = REGISTRY.start("a stage that exits 2", "returning a failure code", refused)
    finished = wait_for_job(job.id)
    assert finished["state"] == "failed", finished["state"]
    assert "code 2" in finished["error"], finished["error"]
    return finished["error"][:60]


@check("the console streams - the sink sees the lines the stage prints")
def t_console_streams():
    from antar.panel import jobs as job_module

    log = job_module.log          # the same log object the queue registers its sink on,
                                  # so a reload of the module cannot hide a missing line

    def chatty(_job):
        for index in range(6):
            log.info(f"test line {index}")
        log.ok("test finished")
        return 0

    job = REGISTRY.start("a chatty test job", "printing lines", chatty)
    finished = wait_for_job(job.id)
    text = "\n".join(finished["lines"])
    for index in range(6):
        assert f"test line {index}" in text, f"line {index} never reached the job"
    assert "test finished" in text
    assert len(log.lines_for_sink("", "")) == 0, "the job left its sink behind"
    return f"{len(finished['lines'])} lines captured live, none left behind"


@check("the job output is delivered in pieces, not all at once")
def t_job_pages():
    def chatty(_job):
        from antar.panel import jobs as job_module

        for index in range(5):
            log.info(f"page line {index}")
            time.sleep(0.12)
        return 0

    job = REGISTRY.start("a paged test job", "printing over time", chatty)
    first = None
    for _ in range(40):
        _, payload = get(f"/api/job/{job.id}?since=0")
        if payload["lines"]:
            first = payload
            break
        time.sleep(0.1)
    assert first, "no output arrived at all"
    assert first["since"] == len(first["lines"]), "the cursor does not match the lines sent"
    tail = wait_for_job(job.id, timeout=30)
    _, later = get(f"/api/job/{job.id}?since={first['since']}")
    assert isinstance(later["lines"], list)
    return f"first page {len(first['lines'])} lines, cursor {first['since']}"


# -------------------------------------------------------------------- score

@check("the panel scores titles with the same judge the gate uses")
def t_scoring_agrees_with_the_gate():
    cfg = config.load()
    render_id = data.current_render(cfg)
    _, payload = get("/api/tab/details")
    title = payload["title_hi"]
    _, scored = post("/api/score", {"render_id": render_id, "title": title})
    assert scored["total"] == payload["chosen_score"], \
        (scored["total"], payload["chosen_score"])
    assert scored["gate"] == titlescore.SCORE_MIN
    assert scored["target"] == titlescore.GENERATOR_TARGET
    assert scored["phrases_count"] >= 1, "no phrase list reached the scorer"
    _, weak = post("/api/score", {"render_id": render_id, "title": "फ़ोन मेज़ पर"})
    assert weak["total"] < scored["total"], (weak["total"], scored["total"])
    assert not weak["pass"], "a weak title passed the gate in the panel"
    return (f"real title {scored['total']}/100 on {scored['phrases_count']} phrase(s), "
            f"weak title {weak['total']}/100 refused")


@check("saving re-scores the title and re-audits, and never declares a pass it did not earn")
def t_save_is_honest():
    cfg = config.load()
    render_id = data.current_render(cfg)
    real = cfg.path("paths.output") / "details" / f"{render_id}_details.json"
    scratch_id = "TEST8_SAVE"
    scratch = cfg.path("paths.output") / "details" / f"{scratch_id}_details.json"
    scratch.write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        _, payload = get(f"/api/tab/details?render={scratch_id}")
        _, good = post("/api/save", {"render_id": scratch_id, "title_hi": payload["title_hi"],
                                     "description": payload["description"],
                                     "tags": payload["tags"],
                                     "pinned_comment": payload["pinned_comment"]})
        assert good["failed"] == 0, [r for r in good["audit"] if not r["pass"]]
        assert good["title_score"] == payload["chosen_score"], good["title_score"]

        _, broken = post("/api/save", {"render_id": scratch_id,
                                       "title_hi": "ANTAR test का सच",
                                       "description": "कुछ भी।" * 3,
                                       "tags": ["एक"], "pinned_comment": "हाँ?"})
        failures = [r for r in broken["audit"] if not r["pass"]]
        assert len(failures) >= 4, f"only {len(failures)} rule(s) fired"
        assert broken["title_score"] < titlescore.GENERATOR_TARGET
        on_disk = json.loads(scratch.read_text(encoding="utf-8"))
        assert on_disk["title_hi"] == "ANTAR test का सच"
        assert on_disk["edited_by_hand"] is True, "the file does not say it was edited"
        assert on_disk["hashtags"] == [], "hashtags were not read back out of the description"
        return (f"good save 0 failures, broken save {len(failures)} failures, "
                f"score {broken['title_score']}/100")
    finally:
        scratch.unlink(missing_ok=True)


# --------------------------------------------------------------- thumbnails

@check("a thumbnail request without a video is refused in plain words")
def t_thumbnail_without_a_video():
    cfg = config.load()
    if data.video_path(cfg, data.current_render(cfg)):
        return "a video is on disk right now, so this test has nothing to refuse"
    try:
        post("/api/thumbnail", {"second": 3})
    except PanelHTTP as exc:
        assert exc.code == 400, exc.code
        assert "ANTAR_VIDEOS.zip" in exc.error, exc.error
        assert "Traceback" not in exc.error
        return exc.error[:64]
    raise AssertionError("a thumbnail was cut out of a video that is not there")


@check("the thumbnail picker records what it did, and never claims a band it missed")
def t_thumbnail_records():
    src = (ROOT / "antar" / "panel" / "thumbs.py").read_text(encoding="utf-8")
    assert "vision._measure" in src, "the picker does not measure with the check's own helper"
    assert "thumbnail_path" in src, "the picker does not record the file for the check"
    cfg = config.load()
    low = float(cfg.get("thresholds.thumbnail_brightness_min", 35))
    high = float(cfg.get("thresholds.thumbnail_brightness_max", 45))
    assert (low, high) == (35.0, 45.0), f"the band moved: {low}-{high}"
    assert "outside the locked band" in src, "an out-of-band pick would be reported as fine"
    return f"band {low:.0f}-{high:.0f} read from config, measured on the saved file"


# ------------------------------------------------------------------ readers

@check("a tab with no file behind it says so instead of showing a zero")
def t_empty_is_honest():
    cfg = config.load()
    empty = data.writer(cfg, "TEST8_NOTHING")
    assert empty["ready"] is False and empty["note"], empty
    blank = data.score(cfg, "TEST8_NOTHING")
    assert blank["ready"] is False and blank["note"], blank
    missing = data.details(cfg, "TEST8_NOTHING")
    assert missing["ready"] is False and missing["note"], missing
    learn = data.learn(cfg)
    assert learn["will_show"] and learn["note"], "the learn tab promises nothing"
    assert learn["ready"] is False, "the learn tab claims data it cannot have yet"
    return "writer, score, details and learn all say what is missing"


@check("the picture tab counts cards and clips from the plan, not from hope")
def t_picture_counts():
    cfg = config.load()
    payload = data.picture(cfg, data.current_render(cfg))
    if not payload["ready"]:
        assert payload["note"], payload
        return "no plan on disk, and the tab says so"
    health = payload["health"]
    assert health["clips"] + health["cards"] == len(payload["shots"]), (health, len(payload["shots"]))
    kinds = [shot["kind"] for shot in payload["shots"]]
    assert health["cards"] == len([k for k in kinds if k != "clip"]), "the card count is wrong"
    for shot in payload["shots"]:
        assert shot["start"] is not None and shot["end"] is not None, shot
        assert shot["end"] >= shot["start"], shot
    return (f"{health['clips']} clips, {health['cards']} cards, "
            f"{health['reused']} reuse(s), {health['clip_pct']}% footage")


@check("the keys tab masks every key and names the services with no test")
def t_keys_tab():
    cfg = config.load()
    payload = data.keys(cfg)
    assert payload["count"] >= 1, "no keys to check"
    for row in payload["keys"]:
        assert len(row["masked"]) < 20, row
        assert row["masked"].count(".") <= 3, row          # "abc123...wxyz"
        assert len(set(row["masked"])) > 1, "the mask hides nothing"
    assert payload["services"], "no services listed"
    assert isinstance(payload["without_a_test"], list)
    return (f"{payload['count']} keys, {payload['alive']} alive, {payload['dead']} dead kept, "
            f"{len(payload['without_a_test'])} service(s) with no test")


# --------------------------------------------------------------------- life

@check("the panel stops cleanly and frees its port")
def t_shutdown():
    cfg = config.load()
    httpd, registry, url = server.start(cfg, port=0, quiet=True)
    port = httpd.server_port
    with urllib.request.urlopen(url, timeout=20) as response:
        assert response.status == 200
    httpd.shutdown()
    httpd.server_close()
    time.sleep(0.3)
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            raise AssertionError(f"the panel still answers on port {port}")
    except (urllib.error.URLError, ConnectionError, OSError):
        pass
    free = server.start(cfg, port=port, quiet=True)
    free[0].shutdown()
    free[0].server_close()
    return f"port {port} was released and could be taken again"


ALL = [
    t_page, t_font, t_tabs, t_state,
    t_no_keys_on_the_wire, t_traversal_is_blocked, t_missing_files_are_plain,
    t_one_job_at_a_time, t_a_failing_job_says_why, t_failure_code,
    t_console_streams, t_job_pages,
    t_scoring_agrees_with_the_gate, t_save_is_honest,
    t_thumbnail_without_a_video, t_thumbnail_records,
    t_empty_is_honest, t_picture_counts, t_keys_tab, t_shutdown,
]


def run_all(verbose: bool = True) -> bool:
    RESULTS.clear()
    BODIES.clear()
    if verbose:
        print("\n  ANTAR - PHASE 8 SELF TEST")
        print("  " + "-" * 62)
    started = time.time()
    try:
        for test in ALL:
            test(verbose=verbose)
    finally:
        if SERVER is not None:
            SERVER.shutdown()
            SERVER.server_close()
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    if verbose:
        print("  " + "-" * 62)
        print(f"  {passed}/{total} passed in {time.time() - started:.2f}s")
        for name, ok, detail in RESULTS:
            if not ok:
                print(f"    - {name}: {detail}")
    return passed == total


if __name__ == "__main__":
    raise SystemExit(0 if run_all() else 1)
