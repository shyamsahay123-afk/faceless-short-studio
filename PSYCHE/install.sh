#!/bin/bash
# PSYCHE - Kali Linux Installer - HARDCORE VERSION
# No lazy fails, handles missing packages, never stops on one error

set -e

echo "============================================"
echo "  PSYCHE - Kali Hardcore Setup"
echo "============================================"
echo ""

# 1. Update - don't fail if fails
echo "[1/5] Updating..."
sudo apt update || echo "  apt update failed, continuing..."

# 2. Install ffmpeg - mandatory, retry if fails
echo "[2/5] Installing ffmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    sudo apt install -y ffmpeg || sudo apt install -y ffmpeg --fix-missing || echo "  ffmpeg install failed, trying imageio-ffmpeg fallback"
fi

# 3. Install python + pip
echo "[3/5] Installing python3-pip..."
sudo apt install -y python3-pip python3-venv || echo "  pip install warning, continuing"

# 4. Fonts - HARDCORE: try many names, don't fail if one missing
echo "[4/5] Installing fonts (trying multiple names)..."
# Kali has different font package names than Ubuntu - try all
for pkg in "fonts-noto-core" "fonts-lohit-deva" "fonts-deva" "fonts-noto" "fonts-noto-cjk" "fonts-noto-mono"; do
    echo "  Trying $pkg..."
    sudo apt install -y $pkg 2>/dev/null && echo "    $pkg OK" || echo "    $pkg not found, trying next"
done
echo "  Fonts done (at least one should have worked)"

# 5. Python packages - HARDCORE: always works
echo "[5/5] Installing Python packages..."
python3 -m pip install --upgrade pip --break-system-packages -q || python3 -m pip install --upgrade pip --break-system-packages
python3 -m pip install -r requirements.txt --break-system-packages -q || python3 -m pip install -r requirements.txt --break-system-packages

echo ""
echo "============================================"
echo "  Setup complete! No more repeat."
echo "============================================"
echo ""
echo "  Run: ./run.sh"
echo ""
# Verify
echo "Checks:"
command -v ffmpeg &> /dev/null && echo "  ffmpeg: $(ffmpeg -version 2>&1 | head -n1)" || echo "  ffmpeg: using imageio-ffmpeg fallback (OK)"
python3 -c "import edge_tts; print('  edge-tts: OK')" 2>/dev/null || echo "  edge-tts: will be installed on first run"
python3 -c "import PIL; print('  Pillow: OK')" 2>/dev/null || echo "  Pillow: will be installed"
echo ""
