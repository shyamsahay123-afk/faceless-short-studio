"""
ANTAR - the panel.

The operator's window onto the studio. A small local web app: no framework, no
build step, no CDN, nothing to install beyond the standard library. Open the
address in a browser and you get nine tabs - HOME, WRITER, PICTURE, CHECK,
DETAILS, SCORE, KEYS, LEARN, SETTINGS - each reading the files the stages
actually wrote.

    python run.py panel

Two rules run through every tab:

  * the panel and the command line are the same code. A button calls the same
    function `python run.py ...` calls, so what the panel shows and what the
    tool does cannot drift apart;
  * the panel invents nothing. If a number is on screen, it came out of
    `output/` or `config/`. If something is missing, the tab says so in words
    instead of showing a zero that looks like a measurement.
"""

from __future__ import annotations

from . import data, jobs, server, thumbs, views  # noqa: F401
from .server import PanelError, serve, start  # noqa: F401

__all__ = ["data", "jobs", "server", "thumbs", "views", "PanelError", "serve", "start"]
