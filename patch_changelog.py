import sys

with open('/home/user/faceless-short-studio/CHANGELOG.md', 'r') as f:
    content = f.read()

new_log = """
## v1.2.0 - 2026-08-31
* **Sequential List Reveal (Curiosity Fix):** Rewrote the Curiosity Card compiler. Instead of flashing the full list on screen and killing watch time, it now builds the list item by item (1, then 2, then 3) synced to the beat.
"""

content = content.replace("# Studio Changelog / Ledger", "# Studio Changelog / Ledger\\n" + new_log)

with open('/home/user/faceless-short-studio/CHANGELOG.md', 'w') as f:
    f.write(content)
