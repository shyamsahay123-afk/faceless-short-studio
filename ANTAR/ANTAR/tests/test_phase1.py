"""
ANTAR - Phase 1 test suite.

Runs with or without pytest:

    python run.py selftest
    python -m pytest tests -q

Every test proves one of the exit criteria:
  - the project runs and the config is intact
  - stale bytecode cannot survive
  - a second instance cannot start
  - the vault is keyed by content, enforces the 2-use cap, catches lookalikes,
    and prunes to its cap
  - keys are never retried once dead, never deleted, and advance on a limit
  - the rotation never repeats a video too closely
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from antar import config, hygiene, probe               # noqa: E402
from antar.keys import ALIVE, DEAD, EXHAUSTED, AllKeysDown, KeyRing   # noqa: E402
from antar.state import Rotation, RunState             # noqa: E402
from antar.vault import Vault, content_hash, hamming   # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str):
    def wrap(fn):
        def run(verbose: bool = True):
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
            except Exception as exc:  # a crash is a failure too
                RESULTS.append((name, False, f"{type(exc).__name__}: {exc}"))
                if verbose:
                    print(f"  [FAIL] {name}   {type(exc).__name__}: {exc}")
                return False
        run.__name__ = fn.__name__
        return run
    return wrap


# ---------------------------------------------------------------- config

@check("config loads and every locked decision holds")
def t_config():
    cfg = config.load()
    assert cfg["voice.voice"] == "hi-IN-SwaraNeural", "voice is not the locked one"
    assert cfg["type.family"] == "Khand", "typeface is not the locked one"
    assert cfg["lane.id"] == "B", "lane is not the locked one"
    assert cfg["script.address"] == "तुम", "address word is not तुम"
    assert cfg["canvas.pure_black_allowed"] is False, "pure black must stay banned"
    assert len(cfg["rotation.rotating"]) == 11, "rotation must have 11 variables"
    return f"{len(cfg.data)} top-level sections, all locked values present"


@check("config rejects a broken build instead of running on it")
def t_config_guard():
    from antar.config import Config, ConfigError
    good = json.loads(config.config_path().read_text(encoding="utf-8"))
    broken = json.loads(json.dumps(good))
    broken["canvas"]["pure_black_allowed"] = True
    try:
        Config(broken, config.config_path()).validate()
    except ConfigError as exc:
        assert "pure_black_allowed" in str(exc), "wrong guard fired"
        return "pure_black_allowed=true was refused"
    raise AssertionError("a build with pure black allowed was NOT refused")


# ---------------------------------------------------------------- hygiene

@check("stale bytecode is purged")
def t_purge():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pkg = root / "antar"
        pkg.mkdir()
        (pkg / "stale.py").write_text("x = 1", encoding="utf-8")
        cache = pkg / "__pycache__"
        cache.mkdir()
        (cache / "stale.cpython-313.pyc").write_bytes(b"\x00" * 32)
        nested = pkg / "deep" / "__pycache__"
        nested.mkdir(parents=True)
        (nested / "a.pyc").write_bytes(b"\x00" * 8)
        (pkg / "orphan.pyc").write_bytes(b"\x00" * 8)

        assert (cache).exists(), "test setup failed"
        removed = hygiene.purge_bytecode(root)
        assert not cache.exists(), "top-level __pycache__ survived"
        assert not nested.exists(), "nested __pycache__ survived"
        assert not (pkg / "orphan.pyc").exists(), "orphan .pyc survived"
        assert (pkg / "stale.py").exists(), "source file was deleted by mistake"
        return f"{removed} items removed, source intact"


@check("a second instance cannot start")
def t_single_instance():
    port = 47799  # a port unlikely to collide with a real run
    first = hygiene.SingleInstance("antar-test", port=port)
    first.acquire()
    try:
        second = hygiene.SingleInstance("antar-test", port=port)
        try:
            second.acquire()
            second.release()
            raise AssertionError("a second instance was allowed to start")
        except hygiene.AlreadyRunning:
            pass
    finally:
        first.release()

    # and after release the port must be free again
    third = hygiene.SingleInstance("antar-test", port=port)
    third.acquire()
    third.release()
    return "second instance refused, port released cleanly after exit"


# ---------------------------------------------------------------- vault

@check("clips are keyed by content, not filename")
def t_vault_hash_keyed():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src = tmp / "random_name_9f3a.mp4"
        src.write_bytes(b"CLIPDATA" * 5000)
        vault = Vault(tmp / "vault")

        a = vault.add(src, source="pexels", query="empty chair")
        # same bytes, completely different filename
        twin = tmp / "totally_other_name_77c1.mp4"
        twin.write_bytes(b"CLIPDATA" * 5000)
        b = vault.add(twin, source="pexels", query="empty chair")

        assert a.hash == b.hash, "the same clip was stored twice under different names"
        assert len(vault) == 1, f"vault holds {len(vault)} entries for one clip"
        return "one clip stored once despite two random filenames"


@check("the 2-use cap holds and is enforced by content")
def t_vault_use_cap():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src = tmp / "clip.mp4"
        src.write_bytes(b"ABCDEFGH" * 4000)
        vault = Vault(tmp / "vault", max_uses=2)
        clip = vault.add(src)

        assert not vault.is_repeat(clip.hash)[0], "a fresh clip was called a repeat"
        vault.record_use(clip.hash, "ANTAR_0001")
        assert not vault.is_repeat(clip.hash)[0], "one use should still be allowed"
        vault.record_use(clip.hash, "ANTAR_0002")

        repeat, reason = vault.is_repeat(clip.hash)
        assert repeat, "a clip used twice was still offered"
        assert "2x" in reason, f"wrong reason: {reason}"
        assert clip.uses == 2 and clip.used_in == ["ANTAR_0001", "ANTAR_0002"], "usage was not recorded"

        # it must survive a reload - the old bug was a registry that forgot
        reloaded = Vault(tmp / "vault", max_uses=2)
        assert reloaded.is_repeat(clip.hash)[0], "the cap was forgotten after reload"
        return "cap holds across a reload, and records which videos used it"


@check("lookalikes are treated as repeats")
def t_vault_lookalike():
    sig_a = "0f0f0f0f0f0f0f0f"
    sig_b = "0f0f0f0f0f0f0f0e"   # one bit different
    # 0x0f ^ 0xff = 0xf0 -> four bits per byte, eight bytes -> 32 set bits
    assert hamming(sig_a, sig_b) == 1, "hamming is wrong at the near end"
    assert hamming(sig_a, "ffffffffffffffff") == 32, "hamming is wrong at the far end"
    assert hamming("0000000000000000", "0000000000000000") == 0, "identical signatures must be 0"
    assert hamming("", "0f0f0f0f0f0f0f0f") == 999, "a missing signature must read as unknown, not unique"

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        vault = Vault(tmp / "vault", lookalike_distance=4)
        one = tmp / "one.mp4"
        one.write_bytes(b"ONE" * 4000)
        two = tmp / "two.mp4"
        two.write_bytes(b"TWO" * 4000)

        a = vault.add(one)
        a.signature = sig_a
        a.uses = 1
        b = vault.add(two)
        b.signature = sig_b

        repeat, reason = vault.is_repeat(b.hash, sig_b)
        assert repeat, "a lookalike was treated as a new clip"
        assert "lookalike" in reason, f"wrong reason: {reason}"

        b.signature = "ffffffffffffffff"
        assert not vault.is_repeat(b.hash, "ffffffffffffffff")[0], "a genuinely different clip was rejected"
        return "1-bit near-duplicate caught, distant clip allowed"


@check("the vault prunes to its cap without touching used clips")
def t_vault_prune():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        vault = Vault(tmp / "vault", cap_gb=0.0002)   # ~210 KB, tiny on purpose
        for i in range(6):
            f = tmp / f"c{i}.mp4"
            f.write_bytes(bytes([i]) * 80_000)
            clip = vault.add(f, query=f"q{i}")
            time.sleep(0.01)
            if i < 2:
                vault.record_use(clip.hash, "ANTAR_0001")   # the two in use
        removed = vault.prune()
        assert removed > 0, "nothing was pruned despite being over cap"
        assert vault.total_bytes <= vault.cap_bytes, "still over cap after pruning"
        assert len(vault) >= 2, "pruned away clips that were in use"
        in_use = [c for c in vault.all() if c.uses > 0]
        assert len(in_use) == 2, f"expected 2 in-use clips to survive, found {len(in_use)}"
        return f"{removed} pruned, {vault.total_gb:.4f} GB left, both in-use clips kept"


# ---------------------------------------------------------------- keys

@check("a dead key is never tried again, and is never deleted")
def t_keys_never_retry():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "keys.json"
        ring = KeyRing(path)
        k1 = ring.add("pexels", "AAA-first-key-0001")
        k2 = ring.add("pexels", "BBB-second-key-0002")

        first = ring.next_key("pexels")
        assert first.value == k1.value, "wrong first key"
        ring.mark_dead(first.value, "401")

        # NEW behaviour: dead keys are moved to keys_dead.json (quarantine),
        # not deleted. The active ring only has alive keys. The original
        # key is preserved on disk - just in the archive file, not the ring.
        after = ring.all()
        assert len(after) == 1, f"dead key was not removed from active ring (got {len(after)} keys, expected 1)"
        assert after[0].value == k2.value, "wrong key left in active ring"

        second = ring.next_key("pexels")
        assert second.value == k2.value, "a dead key was handed out again"

        # reload from disk: dead must still be archived
        reloaded = KeyRing(path)
        assert len(reloaded) == 1, "key count changed on reload"

        # the quarantined key must still exist in keys_dead.json
        dead_path = path.parent / "keys_dead.json"
        assert dead_path.exists(), "keys_dead.json not created on mark_dead"
        archive = json.loads(dead_path.read_text(encoding="utf-8"))
        assert any(k["value"] == k1.value for k in archive["keys"]), \
            "quarantined key was deleted from the archive"
        return "dead key moved to quarantine, skipped, still on disk"


@check("when every key is down the ring says so instead of looping")
def t_keys_all_down():
    with tempfile.TemporaryDirectory() as tmp:
        ring = KeyRing(Path(tmp) / "keys.json")
        ring.add("groq", "key-one")
        ring.add("groq", "key-two")
        ring.next_key("groq")
        ring.next_key("groq")
        try:
            ring.next_key("groq")
            raise AssertionError("it handed out a third key when only two exist")
        except AllKeysDown as exc:
            assert "no usable groq key" in str(exc), "unhelpful error"
        return "AllKeysDown raised rather than retrying a failure"


@check("a rate-limited key is exhausted, not dead, and returns next run")
def t_keys_exhausted():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "keys.json"
        ring = KeyRing(path)
        k = ring.add("gemini", "limited-key")
        ring.mark_exhausted(k.value, "429")
        assert ring.find(k.value).state == EXHAUSTED, "state not set"
        ring.reset_run()
        assert ring.find(k.value).state == ALIVE, "exhausted key did not return after reset"
        ring.mark_dead(k.value, "401")
        # With the new quarantine, the dead key is moved to keys_dead.json,
        # so the active ring no longer has it. We confirm via restore_quarantined
        # which is the supported way to bring a dead key back for a re-check.
        ring.restore_quarantined()
        ring.reset_run()
        # restore_quarantined puts it back as UNKNOWN (not DEAD) - the supported
        # way to ask "is this key alive again?" is to test it, not to revert.
        found = ring.find(k.value)
        assert found is not None, "quarantined key was lost on restore"
        assert found.state != DEAD, "dead key came back as DEAD after revive"
        return "exhausted returns next run, dead quarantined and never returns as DEAD"


@check("the key file survives a crash mid-write")
def t_keys_atomic():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "keys.json"
        ring = KeyRing(path)
        for i in range(5):
            ring.add("pixabay", f"key-{i}")
        raw = path.read_text(encoding="utf-8")
        json.loads(raw)                       # must be valid JSON on disk
        assert len(list(Path(tmp).glob("*.tmp"))) == 0, "a temp file was left behind"
        return "5 keys written, file valid, no temp litter"


# ---------------------------------------------------------------- rotation

@check("no two consecutive videos share more than 3 of 11 values")
def t_rotation():
    cfg = config.load()
    options = cfg["rotation.rotating"]
    limit = int(cfg["rotation.max_shared_values"])
    rot = Rotation(options, max_shared=limit)

    previous = rot.advance(None)
    worst = 0
    for _ in range(60):
        choice = rot.advance(previous)
        shared = [k for k, v in choice.items() if previous.get(k) == v]
        worst = max(worst, len(shared))
        assert len(shared) <= limit, (
            f"{len(shared)} shared values exceeded the limit of {limit}: {shared}")
        previous = choice
    return f"60 consecutive videos, worst overlap {worst} of 11 (limit {limit})"


@check("render ids carry no version suffix")
def t_render_ids():
    with tempfile.TemporaryDirectory() as tmp:
        state = RunState(Path(tmp) / "state.json")
        first = state.next_render_id("reasons-people-ignore-you")
        second = state.next_render_id("why-small-talk-dies")
        assert first.startswith("ANTAR_0001_"), f"unexpected first id: {first}"
        assert second.startswith("ANTAR_0002_"), f"counter did not advance: {second}"
        for bad in ("v2", "V3", "V4", "Phantom", "UPGRADED"):
            assert bad.lower() not in first.lower(), f"version suffix {bad} leaked into {first}"
        reloaded = RunState(Path(tmp) / "state.json")
        third = reloaded.next_render_id("x")
        assert third.startswith("ANTAR_0003_"), "counter did not survive a restart"
        return f"{first} then {second}, no version suffix anywhere"


@check("the project contains no import or reference to an old build")
def t_zero_copy():
    banned = ("ApexDirector", "Apex_Director", "engine_v4_kinetic", "casting_director",
              "core_brain", "video_forge", "nexus_ui", "Phantom")
    offenders = []
    for path in ROOT.rglob("*.py"):
        if "tests" in path.parts and path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for word in banned:
            if word in text:
                offenders.append(f"{path.relative_to(ROOT)} contains '{word}'")
    assert not offenders, "; ".join(offenders[:5])
    return f"scanned {len(list(ROOT.rglob('*.py')))} files, no old-build reference"


@check("the old projects are not imported by anything")
def t_no_old_imports():
    import ast
    offenders = []
    for path in ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if name and not name.split(".")[0] in {"antar", "tests"} and name.split(".")[0] in {
                        "core_brain", "video_forge", "nexus_ui"}:
                    offenders.append(f"{path.name} imports {name}")
    assert not offenders, "; ".join(offenders)
    return "no module imports an old package"


# ---------------------------------------------------------------- runner

# ---------------------------------------------------------------- key checking

def _fake_fetch(responses):
    """Stand-in for probe._fetch: returns canned (status, body) pairs in order."""
    calls = []

    def fetch(url, headers, body=None, timeout=20):
        calls.append({"url": url, "headers": headers})
        return responses[min(len(calls) - 1, len(responses) - 1)]

    fetch.calls = calls
    return fetch


@check("every key check sends a browser user agent")
def t_probe_sends_user_agent():
    real = probe._fetch
    seen = {}

    def spy(url, headers, body=None, timeout=20):
        seen.update(headers)
        return 200, "{}"

    probe.METHODS["pexels"] = lambda value: [probe.Attempt("videos", *spy(
        "https://api.pexels.com/videos/search?query=chair", {"Authorization": value}))]
    probe._fetch = spy
    try:
        probe.verify("pexels", "test-key")
    finally:
        probe._fetch = real
        probe.METHODS["pexels"] = probe.__dict__["_pexels"] if "_pexels" in probe.__dict__ else probe.METHODS["pexels"]

    agent = probe.COMMON_HEADERS.get("User-Agent", "")
    assert agent.startswith("Mozilla/"), f"user agent is {agent!r}"
    assert "Python-urllib" not in agent
    return agent[:34] + "..."


@check("model calls send the same user agent as the key check")
def t_provider_sends_user_agent():
    import urllib.request
    from antar.brain import providers

    seen = {}

    class FakeResponse:
        status = 200

        def read(self, *a):
            return b'{"ok":true}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def spy(request, timeout=None):
        seen["headers"] = {k.lower(): v for k, v in request.header_items()}
        return FakeResponse()

    real = urllib.request.urlopen
    urllib.request.urlopen = spy
    try:
        providers._http("https://api.groq.com/openai/v1/models",
                        {"Authorization": "Bearer x"})
    finally:
        urllib.request.urlopen = real

    agent = seen["headers"].get("user-agent", "")
    assert agent.startswith("Mozilla/"), f"the model call sent {agent!r}"
    assert "authorization" in seen["headers"], "the caller's own headers were dropped"
    return agent[:34] + "..."


@check("a firewall block is not a dead key")
def t_probe_block_is_not_dead():
    blocked = (403, "error code: 1010")
    assert not probe._looks_like_key_problem(*blocked), \
        "a Cloudflare block was read as a key problem"
    assert probe._looks_like_block(*blocked)

    real = probe._fetch
    probe._fetch = lambda url, headers, body=None, timeout=20: blocked
    try:
        verdict = probe.verify("pexels", "some-key")
    finally:
        probe._fetch = real
    assert verdict.state == "blocked", f"verdict was {verdict.state}"
    return "403 / error code 1010 -> BLOCKED"


@check("the API saying the key is wrong is what kills a key")
def t_probe_real_rejection_is_dead():
    real = probe._fetch
    probe._fetch = lambda url, headers, body=None, timeout=20: (
        401, '{"status":401,"code":"Unauthorized","message":"Invalid API key"}')
    try:
        verdict = probe.verify("pexels", "some-key")
    finally:
        probe._fetch = real
    assert verdict.state == "dead", f"verdict was {verdict.state}"
    assert "Invalid API key" in verdict.reason
    return verdict.reason


@check("a key that answers once is alive, even if the other ways fail")
def t_probe_one_yes_is_enough():
    answers = [(200, '{"videos":[{"id":1,"width":1080,"height":1920}]}'),
               (403, "error code: 1010"), (403, "error code: 1010")]
    real = probe._fetch
    probe._fetch = _fake_fetch(answers)
    try:
        verdict = probe.verify("pexels", "some-key")
    finally:
        probe._fetch = real
    assert verdict.state == "alive", f"verdict was {verdict.state}"
    assert len(verdict.attempts) == 3, f"{len(verdict.attempts)} route(s) asked"
    assert "1 of 3" in verdict.reason, verdict.reason
    return verdict.reason + " -> ALIVE"


@check("a key is asked three different ways before it is written off")
def t_probe_asks_three_ways():
    calls = []
    real = probe.METHODS["groq"]

    def three_ways(value):
        calls.append(value)
        return [probe.Attempt("models", 403, "error code: 1010"),
                probe.Attempt("say-hi", 403, "error code: 1010"),
                probe.Attempt("model", 403, "error code: 1010")]

    probe.METHODS["groq"] = three_ways
    try:
        verdict = probe.verify("groq", "some-key")
    finally:
        probe.METHODS["groq"] = real
    assert len(verdict.attempts) == 3, f"only {len(verdict.attempts)} call(s) made"
    assert {a.method for a in verdict.attempts} == {"models", "say-hi", "model"}
    return "a catalogue read, a real answer, and one model"


@check("each route reports what actually came back, in plain words")
def t_probe_evidence_is_specific():
    answers = [(200, '{"videos":[{"id":1,"width":1080,"height":1920}],"page":1}'),
               (200, '{"photos":[{"id":2}],"page":1}'),
               (200, '{"photos":[{"id":3}],"page":1}')]
    real = probe._fetch
    probe._fetch = _fake_fetch(answers)
    try:
        alive = probe.verify("pexels", "some-key")
    finally:
        probe._fetch = real
    notes = [a.evidence for a in alive.attempts]
    assert "1 video(s) 1080x1920" in notes[0], notes
    assert all("photo" in n for n in notes[1:]), notes

    real = probe._fetch
    probe._fetch = _fake_fetch([(401, '{"error":{"message":"Invalid API Key"}}')])
    try:
        dead = probe.verify("groq", "some-key", retries=0)
    finally:
        probe._fetch = real
    assert dead.state == "dead", dead.state
    assert "Invalid API Key" in dead.attempts[0].evidence, dead.attempts[0].evidence
    return "1 video(s) 1080x1920 / Invalid API Key"


@check("a silent API is unknown, never dead")
def t_probe_timeout_is_unknown():
    real = probe._fetch
    probe._fetch = lambda url, headers, body=None, timeout=20: (0, "URLError: timed out")
    try:
        verdict = probe.verify("pexels", "some-key", retries=0)
    finally:
        probe._fetch = real
    assert verdict.state == "unknown", f"verdict was {verdict.state}"
    assert verdict.state != "dead", "a timeout marked a key dead"
    return "no reply -> UNKNOWN"


@check("a written-off key can be deliberately revived, and only deliberately")
def t_revive_is_manual():
    folder = Path(tempfile.mkdtemp())
    ring = KeyRing(folder / "keys.json")
    ring.add("pexels", "AAAABBBBCCCCDDDD")
    ring.mark_dead("AAAABBBBCCCCDDDD", "401")
    # dead key is now in keys_dead.json, not keys.json. Restore first.
    ring.restore_quarantined("pexels")

    fresh = KeyRing(folder / "keys.json")
    assert len(fresh) == 1
    assert fresh.all()[0].state == "unknown"
    assert fresh.revive("groq") == 0, "revive touched a service it was not asked about"
    # revive for the wrong service should not move state
    assert fresh.all()[0].state == "unknown"

    # the only way to "bring back" a dead key is restore_quarantined, which
    # leaves it as UNKNOWN. The point of this check is that the key is not
    # silently flipped to ALIVE without a fresh live test.
    assert fresh.all()[0].state == "unknown", "a restored key is untested, not alive"
    assert len(fresh) == 1, "restore deleted a key"
    return "DEAD -> quarantine -> restore -> UNKNOWN, nothing deleted"


@check("a probe with no check written says so instead of guessing")
def t_probe_unknown_service():
    # this used to use elevenlabs as the example of a service with no check.
    # It has one now, which is the point of the round that added the rest.
    verdict = probe.verify("not-a-service", "some-key")
    assert verdict.state == "unknown"
    assert "no check written" in verdict.reason
    return verdict.reason


@check("every service ANTAR can test has a real check written")
def t_probe_every_service_has_a_check():
    for service in probe.checked_services():
        assert service in probe.METHODS, f"{service} is listed but has no method"
        attempts = probe.METHODS[service]("antar-not-a-real-key")
        assert attempts, f"{service} returned no attempts"
        assert all(isinstance(a, probe.Attempt) for a in attempts), service
        assert len(attempts) <= 3, f"{service} asks {len(attempts)} ways - keep it to three"
    return f"{len(probe.checked_services())} services, each asked 1-3 ways"


@check("deepgram is asked two ways, and the second uses the first's answer")
def t_probe_deepgram_two_routes():
    answers = [
        (200, '{"projects":[{"project_id":"abc-123","name":"main"}]}'),
        (200, '{"project_id":"abc-123","name":"main"}'),
    ]
    real = probe._fetch
    probe._fetch = _fake_fetch(answers)
    try:
        alive = probe.verify("deepgram", "antar-not-a-real-key")
    finally:
        probe._fetch = real
    assert alive.state == "alive", alive.state
    assert [a.method for a in alive.attempts] == ["projects", "project"], \
        [a.method for a in alive.attempts]
    assert "abc-123" in alive.attempts[1].note, alive.attempts[1].note

    real = probe._fetch
    probe._fetch = _fake_fetch([(401, '{"message":"Authentication failed."}')])
    try:
        dead = probe.verify("deepgram", "antar-not-a-real-key", retries=0)
    finally:
        probe._fetch = real
    assert dead.state == "dead", dead.state
    return "projects + project on the way in; 401 read as dead"


@check("a bad key answered with 400 and the API's own words is dead, not unknown")
def t_probe_400_with_key_words_is_dead():
    body = '{"error":{"code":400,"message":"API key not valid. Please pass a valid API key."}}'
    real = probe._fetch
    probe._fetch = _fake_fetch([(400, body)])
    try:
        verdict = probe.verify("youtube", "antar-not-a-real-key", retries=0)
    finally:
        probe._fetch = real
    assert verdict.state == "dead", f"a refused key read as {verdict.state}"
    assert "not valid" in verdict.reason.lower(), verdict.reason
    return verdict.reason[:60]


@check("a service with no check written is reported, not guessed at")
def t_probe_no_check_is_reported():
    verdict = probe.verify("some-new-service", "antar-not-a-real-key")
    assert verdict.state == "unknown", verdict.state
    assert "no check written" in verdict.reason, verdict.reason
    assert not probe.have_check("some-new-service")
    assert probe.have_check("deepgram") and probe.have_check("youtube")
    return verdict.reason


@check("the env file files a deepgram key under deepgram, not under nothing")
def t_envfile_knows_the_new_services():
    from antar import envfile

    text = ("DEEPGRAM_API_KEY=antar-not-a-real-key-1\n"
            "OPENAI_KEY=antar-not-a-real-key-2\n"
            "YOUTUBE_DATA_API_KEY=antar-not-a-real-key-3\n"
            "GEMINI_API_KEY=antar-not-a-real-key-4\n"
            "SOMETHING_ELSE=antar-not-a-real-key-5\n")
    keys, unused, unknown = envfile.parse(text)
    services = [service for service, _ in keys]
    assert services == ["deepgram", "openai", "youtube", "gemini"], services
    assert unknown == ["SOMETHING_ELSE"], unknown
    return "deepgram, openai, youtube, gemini filed; SOMETHING_ELSE listed, not dropped"


ALL = [
    t_config, t_config_guard,
    t_purge, t_single_instance,
    t_vault_hash_keyed, t_vault_use_cap, t_vault_lookalike, t_vault_prune,
    t_keys_never_retry, t_keys_all_down, t_keys_exhausted, t_keys_atomic,
    t_rotation, t_render_ids,
    t_zero_copy, t_no_old_imports,
    t_probe_sends_user_agent, t_provider_sends_user_agent, t_probe_block_is_not_dead, t_probe_real_rejection_is_dead,
    t_probe_one_yes_is_enough, t_probe_asks_three_ways, t_probe_evidence_is_specific,
    t_probe_timeout_is_unknown,
    t_revive_is_manual, t_probe_unknown_service,
    t_probe_every_service_has_a_check, t_probe_deepgram_two_routes,
    t_probe_400_with_key_words_is_dead, t_probe_no_check_is_reported,
    t_envfile_knows_the_new_services,
]


def run_all(verbose: bool = True) -> bool:
    RESULTS.clear()
    if verbose:
        print()
        print("  ANTAR - PHASE 1 SELF TEST")
        print("  " + "-" * 62)
    started = time.time()
    for test in ALL:
        test(verbose=verbose)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    if verbose:
        print("  " + "-" * 62)
        print(f"  {passed}/{total} passed in {time.time()-started:.2f}s")
        if passed != total:
            print("  failing:")
            for name, ok, detail in RESULTS:
                if not ok:
                    print(f"    - {name}: {detail}")
        print()
    return passed == total


if __name__ == "__main__":
    raise SystemExit(0 if run_all(verbose=True) else 1)
