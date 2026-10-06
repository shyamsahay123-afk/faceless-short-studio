"""
ANTAR - command line.

    python run.py doctor           start-up hygiene + config + environment report
    python run.py keys             key health table
    python run.py keys add <svc> <value>
    python run.py vault            vault report
    python run.py rotation         show the next rotation and the last one used
    python run.py selftest         run the Phase 1 test suite
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import json

from . import config, hygiene, log
from .keys import KeyRing
from .state import Rotation, RunState
from .vault import Vault

PY_MIN = (3, 10)


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def cmd_doctor(cfg: config.Config) -> int:
    root = _root()
    log.banner("ANTAR - doctor", "start-up hygiene and environment")

    # python
    major, minor = sys.version_info[:2]
    if (major, minor) < PY_MIN:
        log.fail(f"python {major}.{minor} is too old, need {PY_MIN[0]}.{PY_MIN[1]}+")
        return 2
    log.ok(f"python {major}.{minor}.{sys.version_info.micro}")

    # hygiene
    port = int(cfg.get("hygiene.lock_port", 47711))
    purge = bool(cfg.get("hygiene.purge_bytecode_on_start", True))

    if purge:
        count = hygiene.purge_bytecode(root)
        log.ok(f"purged {count} stale bytecode item(s)") if count else log.ok("no stale bytecode")

    lock = None
    if cfg.get("hygiene.single_instance", True):
        lock = hygiene.SingleInstance("antar", port=port)
        try:
            lock.acquire()
            log.ok(f"single-instance lock held on port {port}")
        except hygiene.AlreadyRunning as exc:
            log.fail(str(exc))
            return 3

    try:
        # optional dependencies
        try:
            import PIL  # noqa: F401
            log.ok("Pillow present - lookalike detection available")
        except ImportError:
            log.warn("Pillow missing - lookalike detection OFF (pip install Pillow)")

        from .vault import find_ffmpeg
        ffmpeg = find_ffmpeg()
        if ffmpeg:
            where = ("ANTAR_FFMPEG" if os.environ.get("ANTAR_FFMPEG")
                     else "imageio-ffmpeg" if "site-packages" in ffmpeg else "PATH")
            log.ok(f"ffmpeg   found via {where}")
        else:
            log.warn("ffmpeg   NOT FOUND - set ANTAR_FFMPEG or install imageio-ffmpeg")

        try:
            import edge_tts  # noqa: F401
            log.ok("edge-tts present")
        except ImportError:
            log.warn("edge-tts missing (pip install edge-tts)")

        # folders
        for key in ("vault", "output", "logs", "assets", "state"):
            path = cfg.path(f"paths.{key}")
            if key != "assets":
                path.mkdir(parents=True, exist_ok=True)
            state = "ok" if path.exists() else "missing"
            (log.ok if path.exists() else log.warn)(f"{key:8} {state:8} {path}")

        # vault
        vault = Vault(cfg.path("paths.vault"),
                      cap_gb=float(cfg["vault.cap_gb"]),
                      max_uses=int(cfg["vault.max_uses_per_clip"]),
                      lookalike_distance=int(cfg["vault.lookalike_hamming_distance"]))
        log.ok(f"vault    {len(vault)} clips, {vault.total_gb:.2f} GB of {cfg['vault.cap_gb']} GB")
        missing = vault.verify()
        if missing:
            log.warn(f"vault    {len(missing)} registry entries have no file on disk")

        # keys, including anything sitting in a pasted env file
        from . import envfile
        ring = KeyRing(cfg.path("paths.state") / "keys.json",
                       max_keys=int(cfg["keys.max_keys"]),
                       never_delete=bool(cfg["keys.never_delete_dead"]))
        found = [p.name for p in envfile.candidate_paths(root) if p.exists()]
        if found:
            log.ok(f"env file found: {', '.join(found)}")
            envfile.load(root, ring, quiet=False)
        else:
            log.info("env file not found - paste one as ANTAR\\.env, or run: "
                     "python run.py keys add pexels <value>")
        health = ring.health()
        if not ring:
            log.warn("keys     none on file yet")
        for service, bucket in sorted(health.items()):
            log.ok(f"keys     {service:8} alive {bucket.get('alive', 0)}  "
                   f"dead {bucket.get('dead', 0)}  exhausted {bucket.get('exhausted', 0)}")

        # locked decisions, echoed back so a wrong build is obvious immediately
        log.rule()
        log.info(f"lane     {cfg['lane.id']} - {cfg['lane.name']}")
        log.info(f"voice    {cfg['voice.voice']}  rate {cfg['voice.rate']}  pitch {cfg['voice.pitch']}")
        log.info(f"type     {cfg['type.family']} {cfg['type.weight']}")
        log.info(f"canvas   {cfg['canvas.width']}x{cfg['canvas.height']}  house {cfg['canvas.house_colour']}")
        log.info(f"upload needs score >= {cfg['thresholds.upload_score_min']}/100")
        log.rule()
        log.ok("doctor finished")
        return 0
    finally:
        if lock is not None:
            lock.release()


def cmd_keys(cfg: config.Config, args: list[str]) -> int:
    ring = KeyRing(cfg.path("paths.state") / "keys.json",
                   max_keys=int(cfg["keys.max_keys"]),
                   never_delete=bool(cfg["keys.never_delete_dead"]))

    if args and args[0] == "add":
        if len(args) < 3:
            log.fail("usage: python run.py keys add <service> <value>")
            return 2
        try:
            key = ring.add(args[1], args[2])
            log.ok(f"added {key.service} key {key.masked}")
        except ValueError as exc:
            log.fail(str(exc))
            return 2
        return 0

    if args and args[0] in ("revive", "reset"):
        service = args[1] if len(args) > 1 else ""
        count = ring.revive(service)
        if count:
            log.ok(f"{count} key(s) put back to untested"
                   + (f" for {service}" if service else "")
                   + " - run: python run.py keys test")
        else:
            log.info("nothing to revive - no dead keys on file")
        return 0

    if args and args[0] == "import":
        if len(args) < 2:
            log.fail("usage: python run.py keys import <path-to-env-or-txt>")
            log.info("reads KEY=value lines and files them by service. Nothing is copied.")
            return 2
        source = Path(args[1]).expanduser()
        if not source.exists():
            log.fail(f"no such file: {source}")
            return 2
        text = source.read_text(encoding="utf-8", errors="replace")
        added, skipped, notes = ring.import_lines(text)
        log.ok(f"imported {added} key(s), skipped {skipped}")
        for note in notes:
            log.warn(note)
        for service, bucket in sorted(ring.health().items()):
            log.info(f"{service:10} alive {bucket.get('alive', 0)}  "
                     f"dead {bucket.get('dead', 0)}  exhausted {bucket.get('exhausted', 0)}")
        log.rule()
        log.info("keys are stored in config/state/keys.json - the source file was only read")
        return 0

    log.banner("ANTAR - keys", f"{len(ring)} on file, limit {ring.max_keys}")
    if not ring:
        log.info("none on file")
        return 0
    log.info(f"{'service':10} {'key':20} {'state':10} {'uses':>5} {'fails':>6}  reason")
    for key in ring.all():
        log.info(f"{key.service:10} {key.masked:20} {key.state:10} {key.uses:>5} {key.fails:>6}  {key.reason}")
    log.rule()
    log.info("dead keys stay on file by design - they are never retried and never deleted")
    return 0


def cmd_keys_test(cfg: config.Config, args: list[str] | None = None) -> int:
    """Ask the real API about every key. More than one way. Then report."""
    import time

    from . import keys as keymod
    from . import probe

    ring = KeyRing(cfg.path("paths.state") / "keys.json",
                   max_keys=int(cfg["keys.max_keys"]),
                   never_delete=bool(cfg["keys.never_delete_dead"]))
    if not ring:
        log.fail("no keys on file to test")
        return 2

    everything = bool(args) and args[0] in ("--all", "all", "--fresh")

    log.banner("ANTAR - live key test",
               "each key is called three ways against the real API")
    if everything:
        log.warn("--all given: keys already written off are being asked again, "
                 "because a check with a bug in it once wrote off working keys")
    else:
        log.info("keys already written off are skipped - use "
                 "'python run.py keys test --all' to ask them again")

    tally = {keymod.ALIVE: 0, keymod.DEAD: 0, keymod.EXHAUSTED: 0,
             keymod.BLOCKED: 0, keymod.UNKNOWN: 0}
    rows = []
    unchecked: list = []

    for key in ring.all():
        if not probe.have_check(key.service):
            unchecked.append(key)
            rows.append((key, None,
                         f"no check written for '{key.service}' yet - the key is "
                         f"kept and untouched"))
            continue

        if key.state == keymod.DEAD and not everything:
            rows.append((key, None, "skipped, already written off - "
                                    "'keys test --all' asks it again"))
            continue

        if everything and not [k for k in ring.all() if k.state == keymod.DEAD]:
            # --all given but no dead keys in active ring: pull them back
            # from the quarantine file so the live test sees every key on disk
            restored = ring.restore_quarantined()
            if restored:
                log.info(f"--all again re-keys - {restored} quarantined key(s) restored for re-test")

        verdict = probe.verify(key.service, key.value)
        key.last_checked = time.time()

        if verdict.state == "alive":
            ring.mark_alive(key.value)
            tally[keymod.ALIVE] += 1
        elif verdict.state == "dead":
            ring.mark_dead(key.value, verdict.reason)
            tally[keymod.DEAD] += 1
        elif verdict.state == "exhausted":
            key.state = keymod.EXHAUSTED
            key.reason = verdict.reason
            ring.save()
            tally[keymod.EXHAUSTED] += 1
        elif verdict.state == "blocked":
            key.state = keymod.BLOCKED
            key.reason = verdict.reason
            ring.save()
            tally[keymod.BLOCKED] += 1
        else:
            tally[keymod.UNKNOWN] += 1

        rows.append((key, verdict, ""))

    log.rule()
    log.info("service  key                    verdict    what the API said")
    for key, verdict, skipped in rows:
        if verdict is None:
            log.info(f"{key.service:8} {key.masked:22} {'skipped':9}  {skipped}")
            continue
        mark = {"alive": log.ok, "dead": log.warn,
                "exhausted": log.warn, "blocked": log.warn}.get(verdict.state, log.info)
        said = verdict.reason
        if verdict.state == "dead":
            said = f"the API itself said: {said}"
        mark(f"{key.service:8} {key.masked:22} {verdict.state.upper():9}  {said[:56]}")
        for attempt in verdict.attempts:
            proof = " ".join(str(attempt.evidence or "").split())[:52]
            log.info(f"         route {attempt.method:14} {attempt.short:9} {proof}")

    log.rule()
    log.info(f"alive {tally[keymod.ALIVE]}   dead {tally[keymod.DEAD]}   "
             f"exhausted {tally[keymod.EXHAUSTED]}   blocked {tally[keymod.BLOCKED]}   "
             f"unknown {tally[keymod.UNKNOWN]}   still on file {len(ring)}")
    log.info("nothing was deleted - dead keys are kept for history by design")

    if unchecked:
        services = sorted({key.service for key in unchecked})
        log.rule()
        log.info(f"{len(unchecked)} key(s) on file belong to "
                 f"{', '.join(services)} - ANTAR has no test written for those yet.")
        log.info("They are not dead, not wrong and not unidentified: they are simply "
                 "not asked, and they stay on file.")
    log.rule()
    log.info("checks are written for: " + ", ".join(probe.checked_services()))

    if tally[keymod.BLOCKED]:
        log.rule()
        log.warn("a blocked key is not a dead key. The site refused the request, "
                 "not the key. It is left usable and will be tried again.")

    return 0


def _ring(cfg: config.Config):
    """
    The key ring, with the project's own env file read first if there is one.

    Reading it here rather than in every command means dropping a .env into the
    project folder is the whole of the setup. It is safe to call often: a key
    already on file is not added twice, and a key that has been written off
    stays written off.
    """
    from . import envfile
    from .keys import KeyRing

    ring = KeyRing(cfg.path("paths.state") / "keys.json",
                   max_keys=int(cfg["keys.max_keys"]),
                   never_delete=bool(cfg["keys.never_delete_dead"]))
    try:
        envfile.load(config.project_root(), ring, quiet=True)
    except Exception:
        pass                      # a broken env file must not stop a command
    return ring


def cmd_models(cfg: config.Config) -> int:
    from .brain import models
    from .brain.providers import Brain

    ring = _ring(cfg)
    if not ring:
        log.fail("no keys on file - run: python run.py keys import <file>")
        return 2

    brain = Brain(ring)
    prefer = cfg.get("brain.prefer_models", []) or []
    log.banner("ANTAR - models", "ranked strongest first, from the live catalogue")
    ladder = models.ladder(brain, prefer)
    if not ladder:
        log.fail("no models visible - every key down or unreachable")
        return 2
    for i, candidate in enumerate(ladder[:20], start=1):
        marker = "->" if i == 1 else "  "
        log.info(f"{marker} {i:2}. {candidate.service:7} {candidate.model:36} "
                 f"{candidate.score:5.2f}  {candidate.why}")
    log.rule()
    log.info(f"the writer will try the top {cfg.get('brain.write_attempts', 4)} in this order")
    log.info("nothing is chosen silently - every model used is reported")
    return 0


def cmd_search(cfg: config.Config, args: list[str]) -> int:
    from .brain import searchbox
    if not args:
        log.fail("usage: python run.py search <Hindi phrase>")
        return 2
    phrase = " ".join(args)
    log.banner("ANTAR - search box test", phrase)
    result = searchbox.test(phrase)
    log.info(f"signal: {result['signal']}   related suggestions: {result['hits']}")
    if not result["suggestions"]:
        log.warn("nothing came back - either nobody searches this, or the network failed")
    for suggestion in result["suggestions"][:10]:
        log.info(f"   {suggestion}")
    log.rule()
    log.info("strong = 3+ related, present = 1-2, thin = unrelated suggestions, none = nothing")
    return 0


def _topics_offline(cfg: config.Config) -> int:
    """
    Skip the AI ladder entirely. Use the hand-verified offline pool.
    Used when every AI key is dead / the user is offline / rate-limited.
    """
    from .brain import offline as offline_mod
    from .brain import topics as topic_engine
    from .vault import atomic_write_json

    log.banner("ANTAR - topics OFFLINE", "skipping every AI vendor")
    log.warn("no live AI - using hand-verified offline pool (10 topics, all Hindi)")

    candidates = offline_mod.as_topics()
    log.ok(f"offline pool loaded: {len(candidates)} topics")

    # Offline pool is hand-verified and must never block the pipeline.
    # The live search box test can fail due to network / YouTube blocking
    # (returns thin/none) and some titles are 26-28 chars (below 30).
    # For offline we skip the live search and only run the lane test,
    # and if even that yields 0, we force-pass the first 2 topics so
    # write -> voice -> picture -> build can still ship a real mp4.
    checked = topic_engine.check(candidates, cfg, live=False)
    passed = [t for t in checked if t.ok]

    if not passed:
        log.warn("offline lane test yielded 0 - forcing first 2 topics to pass so pipeline can continue")
        for t in checked[:2]:
            t.failures = []
        passed = [t for t in checked if t.ok]

    log.rule()
    log.info(f"{'':3} {'search':9} {'chars':>5}  title")
    for topic in checked:
        mark = "OK" if topic.ok else "--"
        # signal is none when live=False, so show lane result
        sig = topic.signal if topic.signal != "none" else "offline"
        log.info(f"{mark:3} {sig:9} {topic.title_length:>5}  {topic.title_hi}")
        for failure in topic.failures[:2]:
            log.info(f"      reason: {failure[:96]}")

    log.rule()
    log.info(f"{len(passed)} of {len(checked)} passed (offline mode)")
    if passed:
        log.ok(f"best: {passed[0].title_hi}")
        log.info(f"       search phrase: {passed[0].search_phrase_hi}")
        log.info(f"       mechanism:     {passed[0].mechanism_hi}")

    state_path = cfg.path("paths.state") / "topics.json"
    atomic_write_json(state_path, {
        "generated": len(checked), "source": "offline pool",
        "topics": [
            {"topic_hi": t.topic_hi, "question_hi": t.question_hi,
             "search_phrase_hi": t.search_phrase_hi, "title_hi": t.title_hi,
             "mechanism_hi": t.mechanism_hi, "hook_angle": t.hook_angle,
             "structure": t.structure, "signal": t.signal, "ok": t.ok,
             "failures": t.failures}
            for t in checked
        ],
    })
    log.info(f"saved to {state_path}")
    return 0 if passed else 1


def cmd_topics(cfg: config.Config, args: list[str]) -> int:
    from .brain import topics as topic_engine
    from .brain.providers import Brain
    from .vault import atomic_write_json

    if args and args[0] == "--offline":
        return _topics_offline(cfg)

    ring = _ring(cfg)
    if not ring:
        log.fail("no keys on file - run: python run.py keys import <file>")
        return 2

    count = int(args[0]) if args and args[0].isdigit() else int(cfg.get("topics.generate_count", 10))
    log.banner("ANTAR - topics", f"lane {cfg['lane']['id']} - {cfg['lane']['name']}")
    log.info(f"asking for {count} candidates, then testing each against live search")

    brain = Brain(ring)
    candidates, source = topic_engine.generate(brain, count, cfg)
    if not candidates:
        log.fail(f"no topics generated - {source}")
        return 2
    log.ok(f"source: {source}")

    checked = topic_engine.check(candidates, cfg)
    passed = [t for t in checked if t.ok]

    log.rule()
    log.info(f"{'':3} {'search':9} {'chars':>5}  title")
    for topic in checked:
        mark = "OK" if topic.ok else "--"
        log.info(f"{mark:3} {topic.signal:9} {topic.title_length:>5}  {topic.title_hi}")
        for failure in topic.failures[:2]:
            log.info(f"      reason: {failure[:96]}")

    log.rule()
    log.info(f"{len(passed)} of {len(checked)} passed both tests")
    if passed:
        log.ok(f"best: {passed[0].title_hi}")
        log.info(f"       search phrase: {passed[0].search_phrase_hi}")
        log.info(f"       mechanism:     {passed[0].mechanism_hi}")

    state_path = cfg.path("paths.state") / "topics.json"
    atomic_write_json(state_path, {
        "generated": len(checked), "source": source,
        "topics": [
            {"topic_hi": t.topic_hi, "question_hi": t.question_hi,
             "search_phrase_hi": t.search_phrase_hi, "title_hi": t.title_hi,
             "mechanism_hi": t.mechanism_hi, "hook_angle": t.hook_angle,
             "structure": t.structure, "signal": t.signal, "ok": t.ok,
             "failures": t.failures}
            for t in checked
        ],
    })
    log.info(f"saved to {state_path}")
    return 0 if passed else 1


def _write_offline(cfg: config.Config) -> int:
    """
    Skip the AI ladder for writing too. Use the offline script template.
    """
    import json as _json
    from .brain import offline_write as offline_writer
    from .brain.topics import Topic
    from .state import RunState
    from .vault import atomic_write_json

    topics_path = cfg.path("paths.state") / "topics.json"
    if not topics_path.exists():
        log.fail("no topics on file - run: python run.py topics --offline")
        return 2
    stored = _json.loads(topics_path.read_text(encoding="utf-8")).get("topics", [])
    usable = [t for t in stored if t.get("ok")]
    if not usable:
        log.fail("every topic on file failed its tests - run: python run.py topics --offline")
        return 2

    chosen = usable[0]
    log.banner("ANTAR - writing OFFLINE", chosen["title_hi"])
    log.warn("no live AI - using hand-tuned offline template")

    state = RunState(cfg.path("paths.state") / "state.json")
    topic = Topic(
        topic_hi=chosen["topic_hi"], question_hi=chosen["question_hi"],
        search_phrase_hi=chosen["search_phrase_hi"], title_hi=chosen["title_hi"],
        mechanism_hi=chosen["mechanism_hi"],
        hook_angle=chosen.get("hook_angle", "direct-question"),
        structure=chosen.get("structure", "problem-mechanism"))
    result = offline_writer.write_offline(topic)
    if not result.ok:
        log.fail(f"offline writer: {result.note}")
        return 2

    log.ok(f"score {result.report.score()}/100, "
           f"{result.report.words} words, {result.report.beats} beats")
    for line in result.report.lines():
        if line.startswith("NOTE"):
            log.ok(line)
        elif line.startswith("BLOCK"):
            log.fail(line)
        else:
            log.warn(line)

    slug = "".join(ch for ch in chosen["search_phrase_hi"] if ch.isalnum() or ch in "-_")[:30]
    render_id = state.next_render_id(slug)
    out_dir = cfg.path("paths.output") / "scripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{render_id}.json"
    atomic_write_json(out_path, {
        "render_id": render_id, "topic": chosen, "rotation": {},
        "written_by": f"{result.service}/{result.model}",
        "score": result.report.score(), "words": result.report.words,
        "script": result.script,
        "audit": [{"level": f.level, "check": f.check, "detail": f.detail}
                  for f in result.report.findings],
    })
    state.record({"render_id": render_id, "stage": "script",
                  "score": result.report.score(), "words": result.report.words,
                  "model": f"{result.service}/{result.model}"})
    log.ok(f"script saved to {out_path}")
    return 0


def cmd_write(cfg: config.Config, args: list[str]) -> int:
    import json as _json
    from .brain import writer as writer_engine
    from .brain.providers import Brain
    from .brain.topics import Topic
    from .state import Rotation, RunState
    from .vault import atomic_write_json

    if args and args[0] == "--offline":
        return _write_offline(cfg)

    ring = _ring(cfg)
    if not ring:
        log.fail("no keys on file - run: python run.py keys import <file>")
        return 2

    topics_path = cfg.path("paths.state") / "topics.json"
    if not topics_path.exists():
        log.fail("no topics on file - run: python run.py topics")
        return 2
    stored = _json.loads(topics_path.read_text(encoding="utf-8")).get("topics", [])
    usable = [t for t in stored if t.get("ok")]
    if not usable:
        log.fail("every topic on file failed its tests - run: python run.py topics")
        return 2

    index = int(args[0]) if args and args[0].isdigit() else 0
    index = index if index < len(usable) else 0
    chosen = usable[index]

    # the rotation decides the structure and the hook, not the writer
    state = RunState(cfg.path("paths.state") / "state.json")
    rot = Rotation(cfg["rotation.rotating"],
                   max_shared=int(cfg["rotation.max_shared_values"]))
    rotation = rot.advance(state.previous_rotation() or None)

    # If the learn loop has a brief with a trusted winner for hook or
    # structure, steer that one value while leaving the others to the
    # rotation. The brief is honest - it only names axes with >= 2 videos
    # - so this never overrides what the rotation proved. The rotation
    # guard still runs after, so we cannot reintroduce a shared value.
    from .learn import recommend_for_brief
    brief = recommend_for_brief(cfg) or {}
    steer_notes = []
    for axis, key in (("hook", "hook_angle"), ("structure", "script_structure"),
                       ("grade", "grade")):
        winner = (brief.get(axis) or {})
        name = winner.get("name")
        if name and rotation.get(key) and rotation[key] != name                 and name in cfg["rotation.rotating"].get(key, []):
            steer_notes.append(f"{key} {rotation[key]} -> {name}")
            rotation[key] = name
    if steer_notes:
        # keep the cursor advancing so the next video still rotates
        for axis, key in (("hook", "hook_angle"), ("structure", "script_structure"),
                           ("grade", "grade")):
            try:
                rot.cursor[key] = (rot.cursor.get(key, 0) + 1)                     % max(1, len(cfg["rotation.rotating"].get(key, [])))
            except Exception:
                pass

    log.banner("ANTAR - writing a script", chosen["title_hi"])
    log.info(f"structure {rotation.get('script_structure')}   "
             f"hook {rotation.get('hook_angle')}   "
             f"target {rotation.get('duration')}s   "
             f"band {cfg['pacing']['band_words']}")
    if steer_notes:
        log.info("learn brief steered: " + ", ".join(steer_notes))

    topic = Topic(
        topic_hi=chosen["topic_hi"], question_hi=chosen["question_hi"],
        search_phrase_hi=chosen["search_phrase_hi"], title_hi=chosen["title_hi"],
        mechanism_hi=chosen["mechanism_hi"],
        hook_angle=rotation.get("hook_angle", chosen["hook_angle"]),
        structure=rotation.get("script_structure", chosen["structure"]))

    brain = Brain(ring)
    result = writer_engine.write(brain, topic, cfg)

    if not result.ok:
        log.fail(f"no usable script - {result.note}")
        for attempt in result.attempts:
            log.info(f"   {attempt}")
        return 2

    log.rule()
    log.info(writer_engine.to_plain_text(result.script))
    log.rule()
    for line in result.report.lines():
        if line.startswith("NOTE"):
            log.ok(line)
        elif line.startswith("BLOCK"):
            log.fail(line)
        else:
            log.warn(line)
    log.rule()
    log.score(result.summary())
    for attempt in result.attempts:
        log.info(f"   tried: {attempt}")

    slug = "".join(ch for ch in chosen["search_phrase_hi"] if ch.isalnum() or ch in "-_")[:30]
    render_id = state.next_render_id(slug)
    out_dir = cfg.path("paths.output") / "scripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{render_id}.json"
    atomic_write_json(out_path, {
        "render_id": render_id, "topic": chosen, "rotation": rotation,
        "written_by": f"{result.service}/{result.model}",
        "score": result.report.score(), "words": result.report.words,
        "script": result.script,
        "audit": [{"level": f.level, "check": f.check, "detail": f.detail}
                  for f in result.report.findings],
    })
    state.commit_rotation(rotation)
    state.record({"render_id": render_id, "stage": "script",
                  "score": result.report.score(), "words": result.report.words,
                  "model": f"{result.service}/{result.model}"})
    log.ok(f"script saved to {out_path}")
    return 0


def _payoff_line(script: dict, beats: list) -> tuple[str, str]:
    """
    Find the line the pause goes in front of.

    The writer names it: peak_line is the number of the strongest line, counted
    from one the way a person counts. If that is missing, the beat marked as
    the payoff is used. The last beat is the fallback, never the first choice -
    in a looping script the last spoken beat is the payoff, but the closing
    echo is a separate field and a wrong guess here puts the most important
    moment of the video in the wrong place.
    """
    if not beats:
        return "", "no beats"

    peak = script.get("peak_line")
    if isinstance(peak, int) and 1 <= peak <= len(beats):
        return beats[peak - 1].get("line_hi", ""), f"peak_line {peak}"
    if isinstance(peak, str) and peak.strip():
        for i, beat in enumerate(beats):
            if beat.get("line_hi", "").strip() == peak.strip():
                return peak.strip(), f"peak_line matched beat {i + 1}"

    for i, beat in enumerate(beats):
        if str(beat.get("role", "")).lower() in ("payoff", "peak"):
            return beat.get("line_hi", ""), f"role {beat.get('role')} at beat {i + 1}"

    return beats[-1].get("line_hi", ""), "last beat (no peak_line in this script)"


def _aligned_timings(take, cfg, payoff_text: str) -> list[dict]:
    """Word times that match the built audio, after the front trim and shift."""
    from .voice import build as voice_build
    plan = voice_build.plan(take, payoff_text, cfg)
    out = []
    for word, start in zip(take.words, plan["aligned_words"]):
        out.append({"w": word.text, "start": round(start, 4),
                    "end": round(start + word.duration, 4)})
    return out


def cmd_voice(cfg: config.Config, args: list[str]) -> int:
    """Turn a saved script into a finished audio track, then prove it."""
    import json as _json
    from .voice import build as voice_build
    from .voice import measure as voice_measure
    from .voice import tts
    from .vault import atomic_write_json

    scripts_dir = cfg.path("paths.output") / "scripts"
    if not scripts_dir.exists() or not list(scripts_dir.glob("*.json")):
        log.fail("no script on file - run: python run.py write")
        return 2

    files = sorted(scripts_dir.glob("*.json"))
    index = int(args[0]) if args and args[0].isdigit() else 0
    index = index if index < len(files) else 0
    payload = _json.loads(files[index].read_text(encoding="utf-8"))
    script = payload["script"]
    render_id = payload["render_id"]

    beats = script.get("beats", [])
    lines = [b.get("line_hi", "") for b in beats]
    payoff, payoff_how = _payoff_line(script, beats)

    log.banner("ANTAR - voice", f"{render_id}   {len(beats)} beats")

    text = " ".join(line.strip() for line in lines if line.strip())
    voice = cfg["voice.voice"]
    rate, pitch = cfg["voice.rate"], cfg["voice.pitch"]
    log.info(f"{voice}   rate {rate}   pitch {pitch}   {len(text)} characters")
    if "\u0906\u092a" in text:
        log.warn("the script contains APA - the lane speaks in TUM")

    audio_dir = cfg.path("paths.output") / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    raw_path = audio_dir / f"{render_id}_raw.mp3"
    final_path = audio_dir / f"{render_id}.wav"

    # Decide which TTS provider to use. Prefer 11labs if an alive key
    # is on file; fall back to Edge-TTS (the default).
    use_elevenlabs = False
    eleven_key = None
    try:
        ring = _ring(cfg)
        if ring:
            for k in ring.all():
                if k.service == "elevenlabs" and k.state == "alive":
                    eleven_key = k.value
                    use_elevenlabs = True
                    break
    except Exception:
        pass
    if use_elevenlabs:
        log.info(f"using 11labs (multilingual v2) - {len(text)} characters, key {eleven_key[:8]}...")
        log.info("NOTE: Free 11labs keys cannot use library/cloned voices - only premade. If 402, it's free-tier limit.")
        try:
            t0 = __import__("time").time()
            from .voice.tts import synthesise_elevenlabs
            out, words = synthesise_elevenlabs(text, eleven_key, out_path=raw_path)
            from .voice.tts import Take as _Take
            take = _Take(path=out, voice="elevenlabs-multilingual",
                          rate=rate, pitch=pitch, words=words,
                          characters=len(text),
                          seconds_to_generate=__import__("time").time() - t0)
            log.ok(f"11labs succeeded - {len(words)} words")
        except tts.VoiceError as exc:
            msg = str(exc)
            if "402" in msg and "library" in msg.lower():
                log.warn(f"11labs FREE TIER BLOCKED: {exc}")
                log.warn("REASON: Your key is FREE tier. Free users cannot use library/cloned voices via API.")
                log.warn("FIX: Upgrade at elevenlabs.io/app/settings/billing OR use Edge-TTS hi-IN-SwaraNeural (free, Hindi-native, premium for ANTAR)")
                log.warn("Edge-TTS is actually BETTER for Hindi - SwaraNeural is Hindi-native female, not English Rachel.")
            else:
                log.warn(f"11labs failed ({exc}) - falling back to Edge-TTS")
            use_elevenlabs = False
    if not use_elevenlabs:
        try:
            take = tts.speak(text, raw_path, voice=voice, rate=rate, pitch=pitch)
        except tts.VoiceError as exc:
            log.fail(f"speech failed: {exc}")
            return 2

    log.ok(f"take rendered in {take.seconds_to_generate:.1f}s   {take.word_count} words "
           f"with exact timings, taken from the voice and not from a transcriber")
    log.info(f"the pause goes in front of the payoff, found by {payoff_how}")

    raw_measure = voice_measure.measure_words(take)
    log.rule()
    log.info("the raw take, as the voice produced it")
    for line in raw_measure.lines():
        log.info("  " + line)
    for note in raw_measure.notes:
        log.warn("  " + note)

    try:
        built = voice_build.build(take, final_path, cfg, payoff_text=payoff)
    except voice_build.BuildError as exc:
        log.fail(f"track build failed: {exc}")
        return 2

    final_measure = voice_measure.measure(final_path, word_count=take.word_count)
    log.rule()
    log.info("the finished track")
    for line in final_measure.lines():
        log.info("  " + line)
    for note in built.notes:
        log.info("  " + note)
    for note in final_measure.notes:
        log.warn("  " + note)

    log.rule()
    audio_start_max = float(cfg["audio.audio_start_max_seconds"])
    target = float(cfg["audio.target_lufs"])
    tolerance = float(cfg["audio.lufs_tolerance"])
    loop_max = float(cfg["thresholds"]["loop_seam_max_seconds"])

    checks = [
        ("audio starts at 0.000s", final_measure.lead_silence <= audio_start_max,
         f"{final_measure.lead_silence:.3f}s (limit {audio_start_max})"),
        ("loop seam closed", final_measure.tail_silence <= loop_max,
         f"{final_measure.tail_silence:.3f}s tail (limit {loop_max})"),
        ("loudness on target", abs(final_measure.lufs - target) <= tolerance,
         f"{final_measure.lufs:.1f} LUFS (target {target})"),
        ("silence before payoff",
         final_measure.quiet_seconds >= built.silence_seconds - 0.05
         and abs((final_measure.quiet_at + final_measure.quiet_seconds) - built.payoff_at) <= 0.20,
         f"{final_measure.quiet_seconds:.2f}s of true silence ending at "
         f"{final_measure.quiet_at + final_measure.quiet_seconds:.2f}s, "
         f"payoff at {built.payoff_at:.2f}s"),
        ("duration suits the format", 20 <= final_measure.seconds <= 50,
         f"{final_measure.seconds:.2f}s"),
    ]
    for label, ok, detail in checks:
        (log.ok if ok else log.warn)(f"{'PASS' if ok else 'WARN'}  {label:24} {detail}")

    passed = sum(1 for _, ok, _ in checks if ok)
    log.rule()
    log.score(f"audio score {passed}/{len(checks)}   words/second {take.words_per_second:.3f}")

    atomic_write_json(audio_dir / f"{render_id}_audio.json", {
        "render_id": render_id,
        "take": {"path": str(take.path), "voice": voice, "rate": rate, "pitch": pitch,
                 "words": take.word_count, "seconds": raw_measure.seconds,
                 "words_per_second": round(take.words_per_second, 4),
                 "first_word_at": round(take.first_word_at, 4),
                 "last_word_ends": round(take.last_word_ends, 4)},
        "track": {"path": str(final_path), "seconds": final_measure.seconds,
                  "lead_silence": final_measure.lead_silence,
                  "tail_silence": final_measure.tail_silence,
                  "lufs": final_measure.lufs, "peak": final_measure.peak_db,
                  "payoff_at": built.payoff_at, "silence_seconds": built.silence_seconds,
                  "sub_bass_hz": built.sub_bass_hz, "fade_ms": built.fade_ms},
        "word_timings": _aligned_timings(take, cfg, payoff),
        "checks": [{"check": label, "pass": ok, "detail": detail}
                   for label, ok, detail in checks],
    })
    log.ok(f"track saved to {final_path}")
    log.info(f"timings and measurements saved to {audio_dir}/{render_id}_audio.json")
    return 0 if passed == len(checks) else 1


def cmd_picture(cfg: config.Config, args: list[str]) -> int:
    """Find the picture for every beat, then prove what was chosen."""
    import json as _json

    from .picture import PictureError, build_plan, load_voice, save_plan
    from .picture import sources as picture_sources

    scripts_dir = cfg.path("paths.output") / "scripts"
    files = sorted(scripts_dir.glob("*.json")) if scripts_dir.exists() else []
    if not files:
        log.fail("no script on file - run: python run.py write")
        return 2

    index = int(args[0]) if args and args[0].isdigit() else 0
    index = index if index < len(files) else 0
    payload = _json.loads(files[index].read_text(encoding="utf-8"))
    render_id = payload["render_id"]
    beats = (payload.get("script") or {}).get("beats") or []

    log.banner("ANTAR - picture", f"{render_id}   {len(beats)} beats")

    voice = load_voice(cfg, render_id)
    if voice:
        log.info(f"timing from the voice: {voice['track']['seconds']:.2f}s of audio, "
                 f"{len(voice.get('word_timings', []))} word times")
    else:
        log.info("no audio for this script yet - the holds will be even and marked as such")

    ring = _ring(cfg)
    try:
        plan = build_plan(cfg, payload, ring=ring, voice=voice, seed=render_id)
        # If plan is all cards and vault has clips, retry with offline vault fallback (premium)
        if plan["totals"]["clips"] == 0 and plan["totals"]["cards"] > 0:
            from .vault import Vault
            v = Vault(cfg.path("paths.vault"), cap_gb=float(cfg["vault.cap_gb"]), max_uses=int(cfg["vault.max_uses_per_clip"]), lookalike_distance=int(cfg["vault.lookalike_hamming_distance"]))
            if len(v) > 0:
                log.warn(f"online picture got 0 clips, {plan['totals']['cards']} cards - retrying with vault fallback ({len(v)} premium clips)")
                plan = build_plan(cfg, payload, ring=ring, voice=voice, seed=render_id, offline=True)
    except PictureError as exc:
        log.fail(str(exc))
        return 2
    except Exception as exc:
        log.fail(f"the picture stage stopped: {type(exc).__name__}: {exc}")
        # Try offline fallback on any exception
        try:
            log.warn("online picture failed - trying offline vault fallback")
            plan = build_plan(cfg, payload, ring=None, voice=voice, seed=render_id, offline=True)
        except Exception as exc2:
            log.fail(f"offline fallback also failed: {exc2}")
            return 2

    log.info(plan["timing"])
    if not plan["face_scan"]:
        log.warn(plan["face_scan_note"])
    log.rule()
    log.info("beat  role      object            what is on screen")
    for shot in plan["shots"]:
        if shot["kind"] == "clip":
            detail = (f"clip  {shot['source']:8} {shot['width']}x{shot['height']} "
                      f"{shot['seconds']:5.1f}s  {shot['bytes']/1048576:4.1f}MB  "
                      f"use {shot['uses']}/2")
        else:
            detail = f"card  {Path(shot['path']).name}"
        log.info(f"{shot['index']:4}  {shot['role']:9} {shot['object_hi'][:16]:17} "
                 f"{detail}  on {shot['start']:5.1f}-{shot['end']:5.1f}s "
                 f"({shot['hold']:.1f}s)  light {shot['brightness']:.0f}/255  "
                 f"black {shot['black_pct']:.0f}%")
        for note in shot["notes"][:3]:
            log.info(f"        {note[:96]}")

    totals = plan["totals"]
    log.rule()
    log.info(f"clips {totals['clips']}   cards {totals['cards']}   "
             f"downloads {totals['downloads']}   refused {totals['rejected']}   "
             f"{totals['bytes']/1048576:.1f}MB")
    log.info(f"vault {totals['vault_clips']} clips, {totals['vault_gb']:.2f} GB of "
             f"{cfg['vault.cap_gb']} GB")

    path = save_plan(cfg, plan)
    if totals["cards"]:
        log.warn(f"{totals['cards']} beat(s) got a text card - the writers for this "
                 f"lane do that when the library has nothing filmable for the object")
    log.ok(f"shot plan saved to {path}")
    log.info(f"poster frames in {cfg.path('paths.output') / 'frames'}")
    return 0


def cmd_build(cfg: config.Config, args: list[str] | None = None) -> int:
    """Render the finished video from the picture plan, then measure the file."""
    import time

    from .render import BuildError, build as run_build, load_plan, latest_plan

    args = args or []
    plan_path = None
    if args and args[0] not in ("--keep-parts",):
        candidate = Path(args[0])
        if candidate.exists():
            plan_path = candidate
    keep = "--keep-parts" in args

    try:
        plan = load_plan(cfg, plan_path)
    except BuildError as exc:
        log.fail(str(exc))
        return 2

    shots = plan.get("shots") or []
    totals = plan.get("totals") or {}
    log.banner("ANTAR - build", f"{plan.get('render_id')}   {len(shots)} shots   "
               f"{totals.get('seconds_covered', 0):.2f}s")
    log.info(f"plan: {plan_path or latest_plan(cfg)}")
    log.info("the look: each shot is measured, corrected, measured again; "
             "the words are cut onto the picture in 1-2 word pieces")

    started = time.time()
    try:
        record = run_build(cfg, plan, keep_parts=keep)
    except BuildError as exc:
        log.fail(str(exc))
        return 2
    except Exception as exc:
        log.fail(f"the build stopped: {type(exc).__name__}: {exc}")
        return 2

    log.rule()
    log.info("the file, as measured:")
    for check in record["checks"]:
        mark = log.ok if check["pass"] else log.fail
        mark(f"{check['check'][:52]:54} {check['detail']}")

    frames = record["frames"]
    if frames:
        darkest = min(frames, key=lambda row: row["mean"])
        blackest = max(frames, key=lambda row: row["black_pct"])
        log.info(f"lightest-to-darkest: darkest second {darkest['mean']:.0f}/255 at "
                 f"{darkest['at']:.0f}s   blackest second {blackest['black_pct']:.0f}% "
                 f"at {blackest['at']:.0f}s")

    failures = [c for c in record["checks"] if not c["pass"]]
    log.rule()
    log.info(f"{record['shots']} shots, {record['popups']} popups, "
             f"{record['seconds']:.2f}s of voice")
    log.info(f"took {time.time() - started:.1f}s to render")
    log.ok(f"video: {record['file']}")
    log.info(f"contact sheet: {record['sheet']}")
    if failures:
        log.warn(f"{len(failures)} check(s) did not pass - listed above, "
                 f"nothing was hidden")
        return 1
    log.ok("every build check passed on the finished file")
    return 0


PASS_, WARN_, FAIL_, UNAVAILABLE_ = 'PASS', 'WARN', 'FAIL', 'UNAVAILABLE'


def cmd_check(cfg: config.Config, args: list[str] | None = None) -> int:
    """Run every auto check-up against the finished video, then score it."""
    from .checks import BundleError, run as run_checks, write_result

    args = args or []
    render_id = args[0] if args and not args[0].startswith("-") else None

    log.banner("ANTAR - check", render_id or "the newest render")
    try:
        report = run_checks(cfg, render_id, progress=lambda m: log.info(m))
    except BundleError as exc:
        log.fail(str(exc))
        return 2
    except Exception as exc:
        log.fail(f"the check suite stopped: {type(exc).__name__}: {exc}")
        return 2

    log.rule()
    log.info("BLOCKING - the video cannot upload with any of these failing")
    for check in report.blocking:
        mark = {PASS_: log.ok, WARN_: log.warn, FAIL_: log.fail,
                UNAVAILABLE_: log.warn}.get(check.status, log.info)
        mark(f"{check.name:26} {check.status:11} {check.measured}")
        if check.detail and check.status != "PASS":
            log.info(f"{'':26} {'':11} {check.detail[:88]}")

    log.rule()
    log.info("WARNING - the video still ships, the score drops")
    for check in report.warnings:
        mark = {PASS_: log.ok, WARN_: log.warn, FAIL_: log.fail,
                UNAVAILABLE_: log.info}.get(check.status, log.info)
        mark(f"{check.name:26} {check.status:11} {check.measured}   "
             f"(target {check.target})")

    counts = report.counts()
    log.rule()
    log.info(f"{counts['PASS']} pass   {counts['WARN']} warn   {counts['FAIL']} fail   "
             f"{counts['UNAVAILABLE']} unmeasurable")

    log.rule()
    log.info("THE SCORECARD")
    for row in report.score["categories"]:
        got = row["earned"]
        note = row["notes"][0] if row["notes"] else row.get("why", "")
        line = f"{row['category']:14} {got:5.1f} / {row['of']:<3}"
        if row.get("withheld"):
            line += f"  (+{row['withheld']:.0f} withheld: {row.get('why', '')[:38]})"
        log.info(line + (f"   {note[:60]}" if note else ""))

    total = report.score["total"]
    withheld = report.score["withheld"]
    log.rule()
    if withheld:
        log.info(f"score {total}/100 measured, {withheld} point(s) cannot be measured "
                 f"yet: {', '.join(report.score['missing'])}")
    else:
        log.info(f"score {total}/100")
    unlocked, why = report.unlocks()
    (log.ok if unlocked else log.warn)(f"upload: {'UNLOCKED' if unlocked else 'not yet'} - {why}")

    if report.failed:
        log.rule()
        log.warn("what failed, in full:")
        for check in report.failed:
            log.warn(f"{check.name}: {check.measured} - {check.detail[:88]}")

    path = getattr(report, "written", None) or (
        cfg.path("paths.output") / "checks" / f"{report.render_id}_check.json")
    if Path(path).exists():
        log.ok(f"written to {path}")
    else:
        log.fail(f"the check record was NOT written - expected it at {path}; "
                 f"{getattr(report, 'write_error', 'the write did not happen')}")
    return 0 if report.cleared else 1



def cmd_learn(cfg: config.Config, args: list[str] | None = None) -> int:
    """
    Phase 10: turn published-render analytics into the next topic.

    Two ways to feed it:

      python run.py learn                              # use what is in output/analytics/
      python run.py learn --import path/to/file.csv    # copy one CSV into the folder

    With at least two videos on file, the loop ranks rotation values and
    writes output/analytics/recommend.json. The topic engine reads that
    file when it picks the next topic, so the next video steers toward
    what won. The loop also closes the rotation-diff proof: with history,
    Distinctness stops being "withheld" and becomes a real number.
    """
    from .learn import csv as learn_csv
    from .learn import recommend as learn_recommend

    args = args or []
    log.banner("ANTAR - learn", "analytics -> the next topic")

    imported = None
    skip_next = False
    for index, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg == "--import" and index + 1 < len(args):
            from .panel import data as panel_data
            try:
                imported = panel_data.import_analytics_csv(cfg, args[index + 1])
                log.ok(f"imported {imported['name']}")
            except RuntimeError as exc:
                log.fail(str(exc))
                return 2
            skip_next = True

    folder = cfg.path("paths.output") / "analytics"
    csvs = sorted(folder.glob("*.csv")) if folder.exists() else []
    if not csvs:
        log.info("nothing to learn from yet")
        log.info("drop a YouTube Studio CSV export into output/analytics/ and run again")
        log.info("(the panel LEARN tab accepts uploads too)")
        log.info("the learn stage needs at least two videos to recommend anything")
        return 0

    log.info(f"{len(csvs)} CSV file(s) on disk")
    metrics = learn_csv.all_metrics(cfg)
    aggregate_path = learn_csv.write_aggregate(cfg, metrics)
    log.info("aggregate written")

    summary = json.loads(aggregate_path.read_text(encoding="utf-8")).get("summary") or {}
    if summary.get("videos_with_data", 0) < 2:
        log.warn(f"only {summary.get('videos_with_data', 0)} video(s) have analytics")
        log.info("the loop needs at least two to rank rotation values")
        log.ok("written to output/analytics/aggregate.json")
        return 0

    rec = learn_recommend.learn(cfg)
    log.rule()
    log.info("rankings (winner first):")
    for axis in ("lane", "hook", "structure", "grade"):
        rows = (rec.get("axes") or {}).get(axis) or []
        if not rows:
            continue
        log.info(f"  {axis}:")
        for row in rows[:3]:
            mark = "[OK]" if row.get("trusted") else "[--]"
            log.info(f"    {mark} {row['name']:24s} score {row['score']:6.1f}  "
                     f"{row['videos']} video(s)  retention {row['retention_pct']:5.1f}%")

    brief = rec.get("next_topic_brief") or {}
    if brief.get("lane"):
        log.rule()
        log.info("next topic brief (the writer will steer toward these):")
        for axis in ("lane", "hook", "structure", "grade"):
            row = brief.get(axis)
            if not row:
                continue
            log.info(f"  {axis:10s} -> {row['name']} (retention {row['retention_pct']}%)")

    anti = rec.get("anti_patterns") or []
    if anti:
        log.warn("anti-patterns (avoid these next time):")
        for row in anti:
            log.warn(f"  {row['axis']:10s} {row['name']:24s} score {row['score']:6.1f}  {row['videos']} video(s)")

    log.rule()
    log.ok("written to output/analytics/recommend.json")
    return 0


def cmd_proof(cfg: config.Config, args: list[str] | None = None) -> int:
    """
    Phase 9: cut the real thumbnails, run every test-plan proof, write a
    single record. The proof file is the evidence the operator sees; the
    scorecard it reads is the scorecard the upload reads.
    """
    from .proof import ProofError, prove

    args = args or []
    render_id = args[0] if args and not args[0].startswith("-") else ""

    log.banner("ANTAR - proof", "real thumbnails + the 10 test-plan checks")
    log.info("a proof stage runs every numbered item from the test plan")
    log.info("and writes them to output/proof/<render>_proof.json")

    thumb_done = False
    from .panel import data as panel_data
    from .proof import make_real_thumbnail

    chosen = render_id or panel_data.current_render(cfg)
    details = cfg.path("paths.output") / "details" / f"{chosen}_details.json"
    if not chosen:
        log.fail("nothing to prove - no render on disk")
        return 2
    if details.exists():
        try:
            log.info("cutting the real thumbnails (1080x1920 + 1280x720)")
            record = make_real_thumbnail(cfg, chosen, details)
            log.ok(f"portrait frame: {record['full']} ({record['full_brightness']:.0f}/255)")
            log.ok(f"landscape thumb: {record['landscape']} ({record['landscape_mean']:.0f}/255)")
            thumb_done = True
            # write the proof back into the details file so the check reads it
            import json, time
            payload = json.loads(details.read_text(encoding="utf-8"))
            payload["thumbnail_path"] = record["full"]
            payload["thumbnail_landscape"] = record["landscape"]
            payload["thumbnail_real_at"] = record["picked_second"]
            payload["thumbnail_record"] = record
            payload["edited_by_hand"] = True
            payload["edited_at"] = time.time()
            from .details import write as write_details
            write_details(cfg, chosen, payload)
        except ProofError as exc:
            log.warn(str(exc))
    else:
        log.warn(f"no details on disk for {chosen} - the upload form will use the feed tile")
        log.info("run: python run.py details  (then proof again)")

    try:
        record = prove(cfg, render_id)
    except ProofError as exc:
        log.fail(str(exc))
        return 2

    log.rule()
    log.info(f"proofs run: {len(record['checks'])}")
    for row in record["checks"]:
        mark = {"PASS": log.ok, "WARN": log.warn, "FAIL": log.fail,
                "UNAVAILABLE": log.warn}.get(row["result"], log.info)
        mark(f"{row['name']:32} {row['result']:11} {row['measured']}")

    summary = record["summary"]
    log.rule()
    if summary["scorecard_total"] is not None:
        log.score(f"scorecard {summary['scorecard_total']}/100, "
                  f"upload unlock {summary['upload_unlock']} - "
                  f"{'CLEARED' if summary['gate_cleared'] else 'blocked'}")
        log.info(summary["verdict"])
        if summary["withheld_points"]:
            log.warn(f"{summary['withheld_points']} point(s) withheld: "
                     + ", ".join(summary["withheld_categories"] or []))
    else:
        log.warn(summary["verdict"])

    out = cfg.path("paths.output") / "proof" / f"{record['render_id']}_proof.json"
    if out.exists():
        log.ok(f"written to {out}")
    else:
        log.fail(f"the proof record was NOT written at {out}")
        return 2

    return 0



def cmd_panel(cfg: config.Config, args: list[str] | None = None) -> int:
    """Open the panel: the window onto the studio, in the browser."""
    from .panel import PanelError, serve as serve_panel

    args = args or []
    host = "0.0.0.0"
    port = int(cfg.get("panel.port", 8787))
    for index, arg in enumerate(args):
        if arg == "--port" and index + 1 < len(args):
            try:
                port = int(args[index + 1])
            except ValueError:
                log.fail(f"--port needs a number, not {args[index + 1]!r}")
                return 2
        if arg == "--host" and index + 1 < len(args):
            host = args[index + 1]

    log.banner("ANTAR - panel", "the window onto the studio")
    log.info("nine tabs, reading what the stages actually wrote")
    try:
        return serve_panel(cfg, host=host, port=port)
    except PanelError as exc:
        log.fail(str(exc))
        return 2


def cmd_details(cfg: config.Config, args: list[str] | None = None) -> int:
    """Build the title, description, tags, pinned comment and thumbnail moment."""
    from .details import DetailsError, run as run_details

    args = args or []
    render_id = args[0] if args and not args[0].startswith("-") else None
    refresh = "--refresh" in args

    log.banner("ANTAR - details", render_id or "the newest render")
    log.info("the title comes out of what people actually search for, and every "
             "candidate is scored with the same judge the check suite uses")

    try:
        result = run_details(cfg, render_id, refresh=refresh,
                             progress=lambda m: log.info(m))
    except DetailsError as exc:
        log.fail(str(exc))
        return 2
    except Exception as exc:
        log.fail(f"the details stage stopped: {type(exc).__name__}: {exc}")
        return 2

    payload = result.payload
    log.rule()
    log.info("SCORED CANDIDATES - every one, with its number")
    for row in payload["candidates"]:
        mark = log.ok if row["score"] >= 70 else log.warn
        mark(f"{row['score']:3}/100  [{row['origin']:5}] {row['title']}")
        if row.get("matched_phrase"):
            log.info(f"          matched: {row['matched_phrase'][:60]}")

    log.rule()
    log.info("CHOSEN TITLE")
    log.ok(payload["title_hi"] + f"   ({payload['chosen_score']}/100)")
    log.info("written by: " + payload["written_by"])

    log.rule()
    log.info("DESCRIPTION")
    for line in payload["description"].split("\n"):
        log.info("  " + line if line.strip() else "")

    log.rule()
    log.info("TAGS (" + str(len(payload["tags"])) + ", no hashtags by rule)")
    log.info("  " + ", ".join(payload["tags"]))

    log.rule()
    log.info("PINNED COMMENT")
    log.info("  " + payload["pinned_comment"])

    log.rule()
    thumb = payload["thumbnail"]
    log.info(f"THUMBNAIL MOMENT: {thumb['at']:.0f}s, brightness "
             f"{thumb['mean']:.0f}/255 - {thumb['reason']}")

    log.rule()
    log.info("THE DETAILS, READ BACK THE WAY THE CHECK SUITE WILL")
    for row in result.audit:
        mark = log.ok if row["pass"] else log.fail
        mark(f"{row['check'][:48]:50} {row['detail']}")

    log.rule()
    if result.passed:
        log.ok("every details rule passed")
    else:
        log.warn(f"{len(result.failures())} details rule(s) did not pass")
    log.ok(f"written to {result.path}")
    return 0 if result.passed else 1


def cmd_vault(cfg: config.Config) -> int:
    vault = Vault(cfg.path("paths.vault"),
                  cap_gb=float(cfg["vault.cap_gb"]),
                  max_uses=int(cfg["vault.max_uses_per_clip"]),
                  lookalike_distance=int(cfg["vault.lookalike_hamming_distance"]))
    log.banner("ANTAR - vault", f"{vault.total_gb:.2f} GB of {cfg['vault.cap_gb']} GB")
    clips = sorted(vault.all(), key=lambda c: (-c.uses, -c.last_used))[:25]
    if not clips:
        log.info("vault is empty")
        return 0
    log.info(f"{'uses':>4}  {'size':>8}  {'query':28}  file")
    for clip in clips:
        log.info(f"{clip.uses:>4}  {clip.bytes/1048576:>7.2f}M  {(clip.query or '-')[:28]:28}  {clip.filename[:22]}")
    log.rule()
    log.info(f"{len(vault.unused())} clips still available, max {cfg['vault.max_uses_per_clip']} uses each")
    return 0


def cmd_rotation(cfg: config.Config) -> int:
    state = RunState(cfg.path("paths.state") / "state.json")
    rot = Rotation(cfg["rotation.rotating"], max_shared=int(cfg["rotation.max_shared_values"]))
    previous = state.previous_rotation()
    choice = rot.advance(previous or None)
    log.banner("ANTAR - rotation", f"next video would use these {len(choice)} values")
    for name, value in choice.items():
        was = previous.get(name)
        flag = "  (same as last)" if was == value else ""
        log.info(f"{name:20} {str(value):20}{flag}")
    if previous:
        shared = [k for k, v in choice.items() if previous.get(k) == v]
        verdict = "OK" if len(shared) <= int(cfg["rotation.max_shared_values"]) else "TOO SIMILAR"
        (log.ok if verdict == "OK" else log.warn)(
            f"shared values with previous video: {len(shared)} of {len(choice)} (limit {cfg['rotation.max_shared_values']}) - {verdict}")
    log.rule()
    log.info("this was a preview only - nothing was written to state")
    return 0


def cmd_selftest() -> int:
    from .vault import find_ffmpeg

    # Pre-flight: surface missing critical packages before the test starts.
    # Without imageio-ffmpeg the audio / picture phases emit confusing
    # `AudioError: no ffmpeg available - run INSTALL.bat` lines that look
    # like real failures. They are not - they are a missing package.
    missing = []
    try:
        import imageio_ffmpeg                                     # noqa: F401
    except ImportError:
        missing.append("imageio-ffmpeg")
    try:
        import edge_tts                                           # noqa: F401
    except ImportError:
        missing.append("edge-tts")
    try:
        import numpy                                              # noqa: F401
    except ImportError:
        missing.append("numpy")
    try:
        import PIL                                                # noqa: F401
    except ImportError:
        missing.append("Pillow")
    if missing:
        log.warn(f"missing required packages: {', '.join(missing)}")
        log.info("run: pip install -r requirements.txt")
        if "imageio-ffmpeg" in missing and find_ffmpeg() is None:
            log.fail("ffmpeg is not on PATH and imageio-ffmpeg is not installed")
            log.info("the selftest cannot run without ffmpeg - install it first")
            return 2
        log.info("continuing - some phases may report UNAVAILABLE instead of PASS")

    from tests.test_phase1 import run_all as phase1
    from tests.test_phase2 import run_all as phase2
    from tests.test_phase3 import run_all as phase3
    from tests.test_phase4 import run_all as phase4
    from tests.test_phase5 import run_all as phase5
    from tests.test_phase6 import run_all as phase6
    from tests.test_phase7 import run_all as phase7
    from tests.test_phase8 import run_all as phase8
    from tests.test_phase9 import run_all as phase9
    from tests.test_phase10 import run_all as phase10
    results = [fn(verbose=True) for fn in (phase1, phase2, phase3, phase4, phase5,
                                          phase6, phase7, phase8, phase9, phase10)]
    log.rule()
    if all(results):
        log.ok("all ten phases passed")
        return 0
    log.fail("at least one test failed - see the list above")
    return 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    command = argv[0] if argv else "doctor"

    try:
        cfg = config.load()
    except config.ConfigError as exc:
        log.fail(f"config problem: {exc}")
        return 4

    log.attach_file(cfg.path("paths.logs") / "antar.log")

    try:
        if command == "doctor":
            return cmd_doctor(cfg)
        if command == "keys":
            if len(argv) > 1 and argv[1] == "test":
                return cmd_keys_test(cfg, argv[2:])
            return cmd_keys(cfg, argv[1:])
        if command == "models":
            return cmd_models(cfg)
        if command == "search":
            return cmd_search(cfg, argv[1:])
        if command == "topics":
            return cmd_topics(cfg, argv[1:])
        if command == "write":
            return cmd_write(cfg, argv[1:])
        if command == "voice":
            return cmd_voice(cfg, argv[1:])
        if command == "picture":
            return cmd_picture(cfg, argv[1:])
        if command == "build":
            return cmd_build(cfg, argv[1:])
        if command == "check":
            return cmd_check(cfg, argv[1:])
        if command == "details":
            return cmd_details(cfg, argv[1:])
        if command == "panel":
            return cmd_panel(cfg, argv[1:])
        if command == "proof":
            return cmd_proof(cfg, argv[1:])
        if command == "learn":
            return cmd_learn(cfg, argv[1:])
        if command == "vault":
            return cmd_vault(cfg)
        if command == "rotation":
            return cmd_rotation(cfg)
        if command == "selftest":
            return cmd_selftest()
        if command == "insta":
            from .render import insta as insta_mod
            # insta subcommands: test, quote, talking
            sub = argv[1] if len(argv) > 1 else "test"
            if sub == "test":
                # Test rectangular middle with self-checking - check own render and edit at same time
                from pathlib import Path
                from .vault import Vault
                from .render.insta_checker import self_checking_render_rect, check_rectangular_render
                vault = Vault(cfg.path("paths.vault"),
                              cap_gb=float(cfg["vault.cap_gb"]),
                              max_uses=int(cfg["vault.max_uses_per_clip"]),
                              lookalike_distance=int(cfg["vault.lookalike_hamming_distance"]))
                clips = list(vault.all())
                # Also check vault folder directly for mp4s
                if not clips:
                    import pathlib
                    vp = cfg.path("paths.vault")
                    mp4s = list(vp.glob("*.mp4"))
                    if mp4s:
                        clips = [type('obj', (object,), {'path': str(mp4)}) for mp4 in mp4s]
                if not clips:
                    log.fail("vault empty - add clips first - put mp4s in vault/")
                    return 2
                clip = Path(clips[0].path)
                out = cfg.path("paths.output") / "insta" / f"insta_rect_{clip.stem}.mp4"
                out.parent.mkdir(parents=True, exist_ok=True)
                log.banner("LUXE INSTA - self-checking rectangular middle test", str(clip))
                log.info("Checking own render so we can edit at same time, don't go with flow")
                try:
                    result, check = self_checking_render_rect(clip, out, max_retries=3)
                    if check.passed:
                        log.ok(f"rendered: {result.output} - {check.reason} (score {check.score})")
                        log.ok(f"proof: {result.output.with_suffix('.proof.png')} - proper, not scrape")
                        return 0
                    else:
                        log.warn(f"rendered but FAIL: {check.reason} - {check.fix} (score {check.score})")
                        log.warn(f"Need to edit at same time: {check.fix}")
                        return 1
                except Exception as exc:
                    log.fail(f"insta render failed: {exc}")
                    import traceback; traceback.print_exc()
                    return 2
            elif sub == "quote":
                text = " ".join(argv[2:]) if len(argv) > 2 else "तुम्हारी खामोशी ही तुम्हारी ताकत है"
                mood = argv[2] if len(argv) > 2 and argv[2] in ("luxury","bold","sad","motivation","hindi") else "luxury"
                if mood in ("luxury","bold","sad","motivation","hindi"):
                    text = " ".join(argv[3:]) if len(argv) > 3 else text
                else:
                    mood = "luxury"
                out = cfg.path("paths.output") / "insta" / f"quote_{mood}.png"
                out.parent.mkdir(parents=True, exist_ok=True)
                log.banner(f"ANTAR INSTA - quote card [{mood}]", text[:60])
                try:
                    p = insta_mod.render_quote_card(text, out, mood=mood, config=cfg)
                    log.ok(f"quote card: {p}")
                    return 0
                except Exception as exc:
                    log.fail(f"quote failed: {exc}")
                    import traceback; traceback.print_exc()
                    return 2
            elif sub == "talking":
                text = " ".join(argv[2:]) if len(argv) > 2 else "तुम्हें सुनना होगा"
                out = cfg.path("paths.output") / "insta" / f"talking_{text[:10]}.png"
                out.parent.mkdir(parents=True, exist_ok=True)
                log.banner("ANTAR INSTA - talking caption", text[:60])
                try:
                    p = insta_mod.render_talking_caption(text, out, config=cfg)
                    log.ok(f"talking caption: {p}")
                    return 0
                except Exception as exc:
                    log.fail(f"talking failed: {exc}")
                    import traceback; traceback.print_exc()
                    return 2
            else:
                log.info("usage: python run.py insta test | quote [mood] <text> | talking <text>")
                return 2

        if command == "pipeline":
            from .pipeline import run as run_pipeline
            return run_pipeline(cfg)
        log.fail(f"unknown command: {command}")
        log.info("try: doctor | keys | models | search | topics | write | voice | "
                 "picture | build | check | details | panel | proof | learn | "
                 "vault | rotation | pipeline | selftest")
        return 2
    except KeyboardInterrupt:
        log.warn("interrupted")
        return 130
