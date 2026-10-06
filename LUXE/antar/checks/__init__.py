"""
ANTAR - the check suite.

Seven blocking rules and eleven warnings, every one of them a number, run
against the finished video and everything that produced it.

    from antar.checks import run, load_bundle

    report = run(config)                 # the newest render
    print(report.counts(), report.unlocks())
"""

from .report import (BLOCKING, FAIL, PASS, UNAVAILABLE, WARN, WARNING, Check,
                     Report, write_json)
from .suite import BundleError, load_bundle, run, run_on, write_result
from . import scorecard, textscan, titlescore, vision

__all__ = [
    "run", "run_on", "load_bundle", "write_result", "BundleError",
    "Report", "Check", "write_json",
    "BLOCKING", "WARNING", "PASS", "WARN", "FAIL", "UNAVAILABLE",
    "scorecard", "textscan", "titlescore", "vision",
]
