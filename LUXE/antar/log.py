"""
ANTAR - logging.

Plain ASCII markers so the output is identical in a Windows console, in a
redirected log file, and in the panel. No emoji, no colour dependency.
"""

from __future__ import annotations

import sys
import threading
from datetime import datetime
from pathlib import Path

_LOCK = threading.Lock()
_LOG_FILE: Path | None = None
_ECHO = True
_SINKS: list = []

MARKERS = {
    "ok": "[OK]",
    "warn": "[WARN]",
    "fail": "[FAIL]",
    "info": "[..]",
    "step": "[>>]",
    "score": "[##]",
}


def attach_file(path: Path) -> None:
    """Mirror all output to a log file (UTF-8, append)."""
    global _LOG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    _LOG_FILE = path


def set_echo(enabled: bool) -> None:
    global _ECHO
    _ECHO = enabled


def add_sink(fn) -> None:
    """
    Watch every line as it is printed.

    The panel uses this: a stage runs in a background thread and the browser
    shows the console as it happens, without the stage knowing anything about
    a browser. A sink that raises must never break a run - a stage losing its
    output to a broken viewer would be worse than the viewer missing a line.
    """
    if fn not in _SINKS:
        _SINKS.append(fn)


def remove_sink(fn) -> None:
    if fn in _SINKS:
        _SINKS.remove(fn)


def lines_for_sink(marker: str, message: str) -> list:
    return list(_SINKS)


def _emit(marker: str, message: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    line = f"{stamp} {marker} {message}"
    with _LOCK:
        if _ECHO:
            try:
                print(line, flush=True)
            except UnicodeEncodeError:
                # a Windows console with a non-UTF-8 code page must never crash a run
                enc = sys.stdout.encoding or "ascii"
                print(line.encode(enc, "replace").decode(enc, "replace"), flush=True)
        if _LOG_FILE is not None:
            with _LOG_FILE.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    for sink in list(_SINKS):
        try:
            sink(marker, message, line)
        except Exception:
            pass


def ok(message: str) -> None:
    _emit(MARKERS["ok"], message)


def warn(message: str) -> None:
    _emit(MARKERS["warn"], message)


def fail(message: str) -> None:
    _emit(MARKERS["fail"], message)


def info(message: str) -> None:
    _emit(MARKERS["info"], message)


def step(message: str) -> None:
    _emit(MARKERS["step"], message)


def score(message: str) -> None:
    _emit(MARKERS["score"], message)


def rule(width: int = 68) -> None:
    _emit("   ", "-" * width)


def banner(title: str, subtitle: str = "") -> None:
    rule()
    _emit("   ", f"  {title}")
    if subtitle:
        _emit("   ", f"  {subtitle}")
    rule()
