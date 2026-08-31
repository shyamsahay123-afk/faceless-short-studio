# Studio Changelog / Ledger

## v1.1.0 - 2026-08-31
* **Version UI:** Added version number to the main Streamlit interface.
* **UI Clean-up:** Removed all references to `@yourchannel` watermark from `app.py`, `video_engine.py`, and `style_engine.py`. Removed confusing Pollinations watermark text.
* **YouTube Shorts Compliance Check:** Added a strict 59.5-second time limit logic. The engine will now forcefully trim any video exceeding this length to guarantee Shorts feed algorithmic compliance.
* **B-Roll Variety Engine (The 'Moon Problem'):** Implemented a state-aware category tracker in `video_engine.py` that bans back-to-back shots of similar cosmic clips (no more three galaxies in a row).
* **PC Watchdog:** Rewrote the generic try/except handler in `daily.py`. It now captures the exact trace of failures (network drops, API quota limits, memory limits), halts the loop immediately instead of wasting PC hours, and generates a massive `CRASH_REPORT.txt`.
