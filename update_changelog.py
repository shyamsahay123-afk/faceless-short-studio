import sys

with open('/home/user/faceless-short-studio/CHANGELOG.md', 'r') as f:
    content = f.read()

new_log = """
## v1.1.1 - 2026-08-31
* **CRITICAL AUDIO FIX (The "Reading the Prompt" Bug):** The text-to-speech engine was accidentally reading the internal script instructions aloud (e.g., "Create an open loop in the first 2 seconds..."). I completely rewrote `clean_script_for_speech()` in `video_engine.py`. It now uses advanced regex (`re.DOTALL`) to aggressively detect and erase multi-line `[PSYCHOLOGY TRIGGER]` instruction blocks before they ever touch ElevenLabs/edge-tts.

"""

content = content.replace("# Studio Changelog / Ledger", "# Studio Changelog / Ledger\\n" + new_log)

with open('/home/user/faceless-short-studio/CHANGELOG.md', 'w') as f:
    f.write(content)

