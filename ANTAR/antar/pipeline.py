"""
ANTAR - one-shot pipeline.

Chains the stages topics -> write -> voice -> picture -> build -> check
so a single BAT click, or a single panel button, makes one finished video.

Each stage calls the same cmd_* functions the CLI uses. If any stage
fails the function returns its non-zero exit code; the BAT prints the
plain-English message above this script's output.

Usage:
    python run.py pipeline
    (same chain the BAT runs)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from antar import config, log  # noqa: E402
from antar.cli import (  # noqa: E402
    cmd_build, cmd_check, cmd_picture, cmd_topics, cmd_voice, cmd_write,
)


STAGES = [
    ("pick a topic",            cmd_topics,  []),
    ("write the Hindi script",  cmd_write,   []),
    ("record the Hindi voice",  cmd_voice,   []),
    ("pick footage for beats",  cmd_picture, []),
    ("build the MP4",           cmd_build,   []),
    ("grade the finished video", cmd_check,   []),
]


def run(cfg: config.Config) -> int:
    log.banner("ANTAR - pipeline", "one render, end to end")
    for index, (label, command, args) in enumerate(STAGES, start=1):
        of = len(STAGES)
        log.info(f"step {index} of {of}: {label}")
        try:
            rc = command(cfg, args)
            # Auto-fallback to offline pool/template when LLM keys are down.
            # This makes the BAT and panel both work without manual CLI.
            if rc not in (0, 1) and label == "pick a topic":
                log.warn("online topics failed - trying offline pool")
                rc = cmd_topics(cfg, ["--offline"])
            if rc not in (0, 1) and label == "write the Hindi script":
                log.warn("online write failed - trying offline template")
                rc = cmd_write(cfg, ["--offline"])
        except Exception as exc:  # last-line safety net
            log.fail(f"step {index} stopped: {type(exc).__name__}: {exc}")
            return 2
        if rc:
            log.fail(f"step {index} ({label}) failed - see the message above")
            return rc
    log.rule()
    log.ok("pipeline finished - the new MP4 is in output/video/")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        cfg = config.load()
    except config.ConfigError as exc:
        log.fail(f"config problem: {exc}")
        return 4
    log.attach_file(cfg.path("paths.logs") / "antar.log")
    return run(cfg)


if __name__ == "__main__":
    raise SystemExit(main())