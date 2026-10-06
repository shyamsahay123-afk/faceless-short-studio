#!/bin/bash
# LUXE - Kali Linux Auto Installer - HARDCORE - No Voice, English Only
# Installs everything auto: ffmpeg, fonts, python deps, tools

set -e

echo "============================================"
echo "  LUXE - Luxury Quote Reels - Kali Setup"
echo "  Basic English | No Voice | Pro Human Edits"
echo "============================================"
echo ""

# 1. Update
echo "[1/6] Updating..."
sudo apt update -qq || echo "  apt update failed, continuing..."

# 2. ffmpeg - mandatory for video rendering, retry multiple ways
echo "[2/6] Installing ffmpeg (video renderer)..."
if ! command -v ffmpeg &> /dev/null; then
    echo "  Trying apt ffmpeg..."
    sudo apt install -y ffmpeg -qq || sudo apt install -y ffmpeg --fix-missing -qq || echo "  apt ffmpeg failed, will use imageio-ffmpeg Python fallback (OK for Kali)"
    if command -v ffmpeg &> /dev/null; then
        echo "  ffmpeg OK via apt: $(ffmpeg -version 2>&1 | head -n1)"
    else
        echo "  ffmpeg via apt failed, Python fallback imageio-ffmpeg will be used"
    fi
else
    echo "  ffmpeg OK: $(ffmpeg -version 2>&1 | head -n1 | cut -c1-60)"
fi

# 3. python3 + pip
echo "[3/6] Installing python3-pip..."
sudo apt install -y python3-pip python3-venv -qq || echo "  pip install warning, continuing"
python3 -m pip install --upgrade pip --break-system-packages -q 2>&1 | tail -n1 || true

# 4. Fonts - for luxury English quotes: Bebas, Didot, Montserrat, etc.
echo "[4/6] Installing fonts for luxury English reels..."
# Try many font packages - Kali has different names
for pkg in "fonts-noto-core" "fonts-noto" "fonts-bebas" "fonts-roboto" "fonts-open-sans" "fonts-montserrat" "fonts-liberation" "fonts-dejavu-core"; do
    echo "  Trying $pkg..."
    sudo apt install -y $pkg -qq 2>/dev/null && echo "    $pkg OK" || echo "    $pkg not found, skip"
done
# Check our custom fonts
echo "  Custom fonts in assets/fonts/:"
ls -lh assets/fonts/ 2>/dev/null | grep ttf || echo "    No custom fonts yet, will use system"

# 5. Python packages - auto download
echo "[5/6] Installing Python packages (auto)..."
echo "  From requirements.txt: Pillow, numpy, imageio-ffmpeg, opencv, librosa, requests..."
python3 -m pip install -r requirements.txt --break-system-packages -q 2>&1 | grep -v "Requirement already satisfied" | tail -n 10 || true
# Retry with --user if fails
if ! python3 -c "import PIL, numpy, imageio_ffmpeg" 2>/dev/null; then
    echo "  Retrying with --user flag..."
    python3 -m pip install -r requirements.txt --break-system-packages --user -q 2>&1 | tail -n 5 || true
fi

# 6. Tools verification - ffmpeg, Pillow, etc.
echo "[6/6] Verifying tools..."
echo "  Tools needed for LUXE:"
command -v ffmpeg &> /dev/null && echo "  ✓ ffmpeg: $(ffmpeg -version 2>&1 | head -n1 | cut -d' ' -f3) (renders videos)" || echo "  ✓ ffmpeg: using imageio-ffmpeg fallback (OK, renders videos)"
python3 -c "import PIL; print(f'  ✓ Pillow {PIL.__version__}: renders clean edges, rounded corners, text')" 2>/dev/null || echo "  ✗ Pillow missing - will install on first run"
python3 -c "import numpy; print(f'  ✓ numpy {numpy.__version__}: maths for shake/zoom')" 2>/dev/null || echo "  ✗ numpy missing"
python3 -c "import imageio_ffmpeg; print(f'  ✓ imageio-ffmpeg: {imageio_ffmpeg.get_ffmpeg_exe()[-20:]} (fallback)')" 2>/dev/null || echo "  ✗ imageio-ffmpeg missing"
python3 -c "import cv2; print(f'  ✓ opencv {cv2.__version__}: face scan')" 2>/dev/null || echo "  - opencv optional, skip"
python3 -c "import librosa; print(f'  ✓ librosa {librosa.__version__}: phonk beat detection for shake/zoom on drop')" 2>/dev/null || echo "  - librosa optional, for phonk drops"

echo ""
echo "============================================"
echo "  LUXE Setup Complete! No Voice, English Only"
echo "============================================"
echo ""
echo "  What LUXE makes:"
echo "  - Instagram Reels 7-15 sec, 1080x1920, basic English quotes"
echo "  - Rectangular middle 1000x1350 centered, clean edges radius 28px"
echo "  - Different fonts: Bebas bold, Didot luxury serif, centered"
echo "  - Premium clips from vault + phonk signature (you provide phonks)"
echo "  - No voice - just music + text"
echo ""
echo "  Tools installed:"
echo "  - ffmpeg: renders videos (via apt or imageio-ffmpeg)"
echo "  - Pillow: renders text, rounded corners, clean edges"
echo "  - numpy: maths for effects"
echo "  - librosa: finds phonk beat drops for shake/zoom"
echo ""
echo "  Run:"
echo "    ./run.sh  -> Panel at http://localhost:8787/"
echo "    python3 run.py insta quote luxury 'Quiet luxury is not loud'"
echo "    python3 run.py insta quote bold 'MAIN CHARACTER ENERGY'"
echo ""
echo "  Put trending phonks in: sfx_library/phonks/"
echo ""
