# Studio Changelog / Ledger\n
## v1.2.1 - 2026-08-31
* **Sentence-Level Visual Sync:** Ripped out the chaotic single-word sync ("word salad"). B-roll is now assigned based on the core thematic concept of the entire 4-6 second sentence.
* **The "2D-to-3D" Trick (Continuous Zoom):** Applied a mandatory 1.0x -> 1.15x Ken Burns scale function to all full-screen B-roll clips so the visual momentum never stops, even on still shots.
\n
## v1.2.0 - 2026-08-31
* **Sequential List Reveal (Curiosity Fix):** Rewrote the Curiosity Card compiler. Instead of flashing the full list on screen and killing watch time, it now builds the list item by item (1, then 2, then 3) synced to the beat.
\n
## v1.1.1 - 2026-08-31
* **CRITICAL AUDIO FIX (The "Reading the Prompt" Bug):** The text-to-speech engine was accidentally reading the internal script instructions aloud (e.g., "Create an open loop in the first 2 seconds..."). I completely rewrote `clean_script_for_speech()` in `video_engine.py`. It now uses advanced regex (`re.DOTALL`) to aggressively detect and erase multi-line `[PSYCHOLOGY TRIGGER]` instruction blocks before they ever touch ElevenLabs/edge-tts.



## v1.1.0 - 2026-08-31
* **Version UI:** Added version number to the main Streamlit interface.
* **UI Clean-up:** Removed all references to `@yourchannel` watermark from `app.py`, `video_engine.py`, and `style_engine.py`. Removed confusing Pollinations watermark text.
* **YouTube Shorts Compliance Check:** Added a strict 59.5-second time limit logic. The engine will now forcefully trim any video exceeding this length to guarantee Shorts feed algorithmic compliance.
* **B-Roll Variety Engine (The 'Moon Problem'):** Implemented a state-aware category tracker in `video_engine.py` that bans back-to-back shots of similar cosmic clips (no more three galaxies in a row).
* **PC Watchdog:** Rewrote the generic try/except handler in `daily.py`. It now captures the exact trace of failures (network drops, API quota limits, memory limits), halts the loop immediately instead of wasting PC hours, and generates a massive `CRASH_REPORT.txt`.
