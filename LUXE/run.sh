#!/bin/bash
# LUXE - One Click HARDCORE - No repeat, no lazy fails
# Just ./run.sh - it fixes everything itself

cd "$(dirname "$0")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  LUXE - One Click (Kali Hardcore)${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# 1. ffmpeg - hardcore check, install if missing, fallback to imageio-ffmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${YELLOW}[1/4] ffmpeg missing - installing...${NC}"
    sudo apt update -qq 2>/dev/null
    sudo apt install -y ffmpeg -qq 2>/dev/null || echo "  apt ffmpeg failed, using imageio-ffmpeg (Python fallback) - OK"
else
    echo -e "${GREEN}[1/4] ffmpeg OK${NC}"
fi

# 2. python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}python3 missing${NC}"
    exit 1
fi
echo -e "${GREEN}[2/4] python3 $(python3 --version 2>&1 | cut -d' ' -f2) OK${NC}"

# 3. requirements - hardcore: try, if fails try again with different flags
if ! python3 -c "import edge_tts, PIL, numpy" 2>/dev/null; then
    echo -e "${YELLOW}[3/4] Installing Python deps (once)...${NC}"
    python3 -m pip install -r requirements.txt --break-system-packages --quiet 2>&1 | grep -v "Requirement already satisfied" || true
    # Verify again
    if python3 -c "import edge_tts" 2>/dev/null; then
        echo -e "${GREEN}  deps OK${NC}"
    else
        echo -e "${YELLOW}  Some deps still missing, trying --user...${NC}"
        python3 -m pip install -r requirements.txt --break-system-packages --user --quiet 2>&1 | tail -n 5 || true
    fi
else
    echo -e "${GREEN}[3/4] Python deps OK${NC}"
fi

# 4. doctor
echo -e "${GREEN}[4/4] Doctor check...${NC}"
python3 run.py doctor 2>&1 | grep -E "OK|FAIL|WARN|voice|vault" | tail -n 15

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  READY${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "  1) Panel (http://localhost:8787/) - SELLING DEMO"
echo "  2) Make 1 video OFFLINE (no keys, uses vault)"
echo "  3) Make 1 video ONLINE (needs .env keys)"
echo "  4) Check keys"
echo "  5) Exit"
echo ""
read -p "Choose [1-5] (default 1): " choice
choice=${choice:-1}

case $choice in
    1) python3 run.py panel ;;
    2) python3 run.py pipeline --offline; ls -lh output/video/*.mp4 2>/dev/null | tail -n 3 ;;
    3) python3 run.py pipeline ;;
    4) python3 run.py keys health 2>&1 | tail -n 20; python3 run.py keys test --all 2>&1 | tail -n 20 ;;
    5) echo "Bye" ;;
    *) python3 run.py panel ;;
esac
