import sys

with open('daily.py', 'r') as f:
    content = f.read()

import_patch = """
import os
import sys
import time
import json
import argparse
import subprocess
import traceback  # For PC watchdog
"""
content = content.replace(
    "import os\nimport sys\nimport time\nimport json\nimport argparse\nimport subprocess",
    import_patch
)

watchdog_catch = """
    except Exception as e:
        crash_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CRASH_REPORT.txt")
        error_trace = traceback.format_exc()
        
        # --- PC WATCHDOG LOGGING ---
        # Capture exact reason: Network, API limit, crash, ZIP, etc.
        reason = "Unknown Crash"
        if "timeout" in str(e).lower() or "connection" in str(e).lower():
            reason = "Network Drop / Timeout"
        elif "402" in str(e) or "429" in str(e) or "budget" in str(e).lower():
            reason = "API Limit / Quota Exceeded"
        elif "zip" in str(e).lower() or "extract" in str(e).lower():
            reason = "Corrupt Download / ZIP Error"
        elif "memory" in str(e).lower():
            reason = "Out of Memory (OOM)"
            
        with open(crash_log_path, "w", encoding="utf-8") as f:
            f.write(f"=== PC WATCHDOG CRASH REPORT ===\\n")
            f.write(f"Time: {time.ctime()}\\n")
            f.write(f"Topic: {topic}\\n")
            f.write(f"Guessed Reason: {reason}\\n")
            f.write(f"Error: {e}\\n\\n")
            f.write(f"Full Traceback:\\n{error_trace}\\n")
            f.write(f"================================\\n")
            
        print(f"\\n[!] WATCHDOG TRIGGERED: {reason}")
        print(f"[!] RENDER FAILED: {e}")
        print(f"[!] Wrote full crash details to {crash_log_path}")
        print(f"[!] HALTING autopilot to save your time.\\n")
        
        try:
            db.update_short_status(short_id, "failed")
        except Exception:
            pass
        
        # We exit completely instead of continuing to next topic to stop eating 3 hours
        sys.exit(1)
"""

# Replace the generic exception block
content = content.replace(
    """    except Exception as e:
        print(f"[4/6] RENDER FAILED: {e} — continuing to next topic.")
        try:
            db.update_short_status(short_id, "failed")
        except Exception:
            pass
        return 1""",
    watchdog_catch
)

with open('daily.py', 'w') as f:
    f.write(content)

print("Patched daily.py with PC watchdog")
