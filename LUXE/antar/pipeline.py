"""
LUXE - one-shot pipeline - No Voice, English Only, Basic English Quotes

Chains: topics -> write -> picture -> build -> check
No voice stage - as per user: we not going to add voice

Usage:
    python run.py pipeline
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from antar import config, log  # noqa: E402
from antar.cli import (  # noqa: E402
    cmd_build, cmd_check, cmd_picture, cmd_topics, cmd_write,
)


STAGES = [
    ("pick English luxury quote topic", cmd_topics,  []),
    ("write English quote (3-8 words)", cmd_write,   []),
    ("pick premium footage",            cmd_picture, []),
    ("build Reel 1080x1920 rectangular middle clean edges", cmd_build,   []),
    ("minimal Insta check (no YT gate)", cmd_check,   []),
]


def run(cfg: config.Config) -> int:
    log.banner("LUXE - pipeline", "English luxury quote reel, no voice, 7-15 sec")
    for index, (label, command, args) in enumerate(STAGES, start=1):
        of = len(STAGES)
        log.info(f"step {index} of {of}: {label}")
        try:
            rc = command(cfg, args)
            if rc not in (0, 1) and label.startswith("pick English"):
                log.warn("online topics failed - trying offline luxury pool")
                rc = cmd_topics(cfg, ["--offline"])
            if rc not in (0, 1) and label.startswith("write English"):
                log.warn("online write failed - trying offline template")
                rc = cmd_write(cfg, ["--offline"])
        except Exception as exc:
            log.fail(f"step {index} stopped: {type(exc).__name__}: {exc}")
            return 2
        if rc:
            log.fail(f"step {index} ({label}) failed - see above")
            return rc
    log.rule()
    log.ok("LUXE pipeline finished - Reel in output/video/ - 1080x1920, basic English, centered, pro human edits")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        cfg = config.load()
    except config.ConfigError as exc:
        log.fail(f"config problem: {exc}")
        return 4
    log.attach_file(cfg.path("paths.logs") / "luxe.log")
    return run(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
