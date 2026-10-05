#!/usr/bin/env python3
"""
ANTAR - entry point.

    python run.py doctor
    python run.py keys
    python run.py vault
    python run.py rotation
    python run.py pipeline          # one render, end to end
    python run.py selftest
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from antar.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())