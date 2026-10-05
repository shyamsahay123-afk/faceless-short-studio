#!/bin/bash
# ANTAR - Linux / Kali version
# Equivalent of ANTAR.bat for Windows

cd "$(dirname "$0")"

clear
echo ""
echo "  ============================================"
echo "     ANTAR - Kali Linux"
echo "  ============================================"
echo ""

if ! command -v python3 &> /dev/null; then
    echo "  Python3 is not installed."
    echo "  Fix: sudo apt update && sudo apt install -y python3 python3-pip"
    exit 1
fi

PYVER=$(python3 --version 2>&1)
echo "  Python found: $PYVER"
echo ""

# Clean pycache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

# Check ffmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "  ffmpeg not found - installing..."
    sudo apt update && sudo apt install -y ffmpeg
fi

# Install requirements
echo "  Installing requirements..."
python3 -m pip install --quiet -r requirements.txt --break-system-packages 2>/dev/null || python3 -m pip install --quiet -r requirements.txt

if [ $? -ne 0 ]; then
    echo "  Could not install requirements. Check internet."
    exit 1
fi

echo ""
echo "  Starting the panel..."
echo "  When you see 'ANTAR panel READY', open http://localhost:8787/ in browser"
echo ""
echo "  ============================================"
echo ""

# Start panel
python3 run.py panel

echo ""
echo "  ============================================"
echo "  Panel stopped."
echo "  ============================================"
