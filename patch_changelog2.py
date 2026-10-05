import sys

with open('/home/user/faceless-short-studio/CHANGELOG.md', 'r') as f:
    content = f.read()

new_log = """
## v1.2.1 - 2026-08-31
* **Sentence-Level Visual Sync:** Ripped out the chaotic single-word sync ("word salad"). B-roll is now assigned based on the core thematic concept of the entire 4-6 second sentence.
* **The "2D-to-3D" Trick (Continuous Zoom):** Applied a mandatory 1.0x -> 1.15x Ken Burns scale function to all full-screen B-roll clips so the visual momentum never stops, even on still shots.
"""

content = content.replace("# Studio Changelog / Ledger", "# Studio Changelog / Ledger\\n" + new_log)

with open('/home/user/faceless-short-studio/CHANGELOG.md', 'w') as f:
    f.write(content)
