#!/bin/bash
# LUXE - Auto Start (no questions)
# For when you want it to just work: ./autostart.sh

cd "$(dirname "$0")"

# Install if needed (silent)
command -v ffmpeg &> /dev/null || sudo apt update -qq && sudo apt install -y ffmpeg -qq
python3 -c "import edge_tts" 2>/dev/null || python3 -m pip install -r requirements.txt --break-system-packages --quiet

# Run panel directly
python3 run.py panel
