PSYCHE on Kali - ONE CLICK

You said: "i dont want to do the same things again and again"

Solution: Use these scripts, not manual commands.

1) FIRST TIME ONLY:
   ./install.sh
   (installs ffmpeg + all python packages)

2) EVERY TIME AFTER:
   ./run.sh
   -> Menu: 1) Panel 2) Make video offline 3) Make video online 4) Check keys

   OR for no menu, just panel:
   ./autostart.sh

That's it. No more repeat commands.

Files:
- PSYCHE.bat = Windows only, ignore on Kali
- PSYCHE.sh = Old Linux script
- install.sh = First time setup
- run.sh = NEW one-click with menu (USE THIS)
- autostart.sh = NEW auto panel (no questions)

Kali commands replaced:
  Windows: PSYCHE.bat
  Kali:    ./run.sh

Requirements auto-handled:
  - ffmpeg: auto-installs if missing
  - edge-tts, Pillow, etc: auto-installs if missing
  - No need to type --break-system-packages manually

Offline mode (no API keys):
  ./run.sh -> choose 2
  Makes video from vault (16 clips) + free Hindi voice

Online mode (needs keys in .env):
  Add keys to .env file, then ./run.sh -> choose 3
