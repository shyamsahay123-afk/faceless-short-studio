"""
ANTAR - hygiene.

Two jobs, both of which exist because of a specific past failure:

1. purge_bytecode() - stale __pycache__ made two builds run at once and
   produced an error message that mixed old text with new logic. ANTAR never
   runs on stale bytecode.

2. SingleInstance - holds a loopback port for the life of the process. If the
   port is taken, another ANTAR is running and this one refuses to start.
   Chosen over a lock file because the OS releases a port when the process
   dies, even on a hard kill. No stale lock can survive a crash.
"""

from __future__ import annotations

import os
import socket
import time
from pathlib import Path

from . import log

BYTECODE_DIRS = ("__pycache__",)

# skip these while walking; they are large and never contain our bytecode
SKIP = {".git", "vault", "output", "node_modules", ".venv", "venv"}


class AlreadyRunning(RuntimeError):
    """Another ANTAR instance holds the lock port."""


def purge_bytecode(root: Path) -> int:
    """
    Delete every __pycache__ directory and .pyc file under root.
    Returns the number of items removed.
    """
    removed = 0
    root = Path(root).resolve()

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [d for d in dirnames if d not in SKIP]

        for name in list(dirnames):
            if name in BYTECODE_DIRS:
                target = Path(dirpath) / name
                for entry in target.rglob("*"):
                    if entry.is_file():
                        entry.unlink(missing_ok=True)
                # remove the now-empty tree, deepest first
                for sub in sorted(target.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                    if sub.is_dir():
                        sub.rmdir()
                try:
                    target.rmdir()
                except OSError:
                    pass
                dirnames.remove(name)
                removed += 1

        for name in filenames:
            if name.endswith((".pyc", ".pyo")):
                try:
                    (Path(dirpath) / name).unlink(missing_ok=True)
                    removed += 1
                except OSError:
                    pass

    return removed


class SingleInstance:
    """
    Context manager. Binds a loopback port for the life of the block.

        with SingleInstance("antar", port=47711):
            ...run the studio...

    Raises AlreadyRunning if the port is already bound.
    """

    def __init__(self, name: str = "antar", port: int = 47711):
        self.name = name
        self.port = port
        self._sock: socket.socket | None = None
        self.acquired_at: float = 0.0

    def acquire(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # deliberately NOT setting SO_REUSEADDR: on Windows it would let a
        # second process bind the same port, which is the exact bug this
        # class exists to prevent.
        try:
            sock.bind(("127.0.0.1", self.port))
            sock.listen(1)
        except OSError as exc:
            sock.close()
            raise AlreadyRunning(
                f"another {self.name} instance is already running "
                f"(lock port {self.port} is taken). Close it and try again."
            ) from exc
        self._sock = sock
        self.acquired_at = time.time()

    def release(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def __enter__(self) -> "SingleInstance":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()

    def __del__(self) -> None:
        self.release()


def prepare(root: Path, port: int = 47711, name: str = "antar") -> SingleInstance:
    """Start-up hygiene: purge bytecode, then claim the single-instance lock."""
    count = purge_bytecode(root)
    if count:
        log.ok(f"purged {count} stale bytecode item(s)")
    else:
        log.ok("no stale bytecode")

    lock = SingleInstance(name=name, port=port)
    lock.acquire()
    log.ok(f"single-instance lock held on port {port}")
    return lock
