# ANTAR on Kali Linux - Guide

You moved from Windows (.bat) to Kali. .bat doesn't work on Linux.

## Quick Start on Kali

```bash
cd ~/ANTAR
chmod +x ANTAR.sh install.sh
./install.sh
./ANTAR.sh
```

Or manually:

```bash
sudo apt update
sudo apt install -y ffmpeg python3-pip
python3 -m pip install -r requirements.txt --break-system-packages
python3 run.py doctor
python3 run.py panel
```

## Files

- `ANTAR.bat` = Windows (old)
- `ANTAR.sh` = Kali/Linux (new) - use this
- `install.sh` = One-time setup for Kali

## Panel

After `./ANTAR.sh`, open:
http://localhost:8787/

## Offline Mode (No API keys needed)

```bash
python3 run.py pipeline --offline
```

Uses vault clips (16 clips included) + Edge-TTS Hindi voice (free, no key).

## If ffmpeg missing

Kali: `sudo apt install ffmpeg`
Check: `ffmpeg -version`

## If edge-tts missing

`python3 -m pip install edge-tts --break-system-packages`

## Persistence on Kali USB

You already made persistence.dat 10GB on D: and copied to USB root with ventoy.json - that setup works for Kali Live USB.

For installed Kali (not Live), no persistence needed - everything saves normally.
