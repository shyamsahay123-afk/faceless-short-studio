import sys

with open('/home/user/faceless-short-studio/CHANGELOG.md', 'r') as f:
    content = f.read()

new_log = """
## v1.2.2 - 2026-08-31
* **Audio Anchor & Voice Overhaul:** Shifted default voice engine to `turbo_v2.5` with conversational settings (lower stability, higher style exaggeration) to eliminate the robotic tone. Added a subconscious tension riser 2 seconds before the main list reveal to anchor viewer attention through the climax.
"""

content = content.replace("# Studio Changelog / Ledger", "# Studio Changelog / Ledger\\n" + new_log)

with open('/home/user/faceless-short-studio/CHANGELOG.md', 'w') as f:
    f.write(content)
