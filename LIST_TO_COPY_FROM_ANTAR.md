# LIST - What to Copy from ANTAR for LUXE & PSYCHE

## User: "i didnot want antar again i want it with other name, copy it because it easy to edit it because u have to do it form starting, 1st list things u should copy from antar then edit them and then gave a COMPLETE ZIP that open proper and have same ui but with diffrent name, same thing we gona do with yt zip"

## ANTAR Structure Analysis:

ANTAR/
├── antar/                  # CORE PACKAGE - COPY ALL
│   ├── __init__.py
│   ├── brain/              # AI writing - topics, writer, offline
│   ├── checks/             # Build verification - scorecard
│   ├── cli.py              # Command line - doctor, pipeline, insta commands
│   ├── config.py           # Config loader - EDIT for new name
│   ├── details/            # Title, description, tags
│   ├── envfile.py          # .env loader
│   ├── hygiene.py          # Single instance, bytecode purge
│   ├── keys.py             # API key rotation
│   ├── learn/              # Analytics -> next topic
│   ├── log.py              # Logging
│   ├── panel/              # UI - SAME UI BUT DIFFERENT NAME - EDIT titles
│   │   ├── server.py       # Panel server - EDIT title
│   │   ├── views.py        # HTML views - EDIT brand name
│   │   ├── thumbs.py       # Thumbnails
│   │   ├── data.py
│   │   └── jobs.py
│   ├── picture/            # Clip search - Pexels, Pixabay, vault
│   ├── pipeline.py         # End-to-end pipeline
│   ├── probe.py            # API key checks
│   ├── proof/              # Thumbnail proof + test-plan
│   ├── render/             # VIDEO RENDERING - MOST IMPORTANT TO EDIT
│   │   ├── render.py       # Full-bleed vertical (YT style)
│   │   ├── insta.py        # NEW - rectangular middle clean edges (LUXE)
│   │   ├── grade.py        # Color grading
│   │   └── typekit.py      # Captions - Khand only -> multi-font for LUXE
│   ├── state.py            # Rotation, run state
│   ├── vault.py            # Premium clip vault - KEEP AS IS (premium clips)
│   └── voice/              # TTS - edge-tts
├── assets/
│   └── fonts/              # COPY - Khand + Bebas + Didot
│       ├── Khand-Bold.ttf
│       ├── BebasNeue-Regular.ttf
│       └── Didot-Placeholder.ttf
├── config/
│   ├── antar.json          # MASTER CONFIG - EDIT for each studio
│   └── insta.json          # Insta track config - COPY to LUXE
├── run.py                  # Entry point - COPY
├── run.sh                  # One-click Kali - COPY + EDIT name
├── install.sh              # One-click install - COPY
├── autostart.sh            # Auto panel - COPY
├── requirements.txt        # Deps - COPY
└── tests/                  # Tests - COPY but not needed for zip

## For LUXE (Instagram Luxury Quote Reels):

COPY:
- antar/ entire package (brain, checks, cli, config, details, envfile, hygiene, keys, learn, log, panel, picture, pipeline, probe, proof, render, state, vault, voice)
- assets/fonts/ all 3 fonts
- run.py, run.sh, install.sh, autostart.sh, requirements.txt
- config/ structure

EDIT:
1. config/luxe.json (new file from antar.json):
   - project.name: "LUXE"
   - project.meaning: "luxury quote reels"
   - lane: from "practical-psychology" to "luxury-quotes" - topics are quotes, not psychology
   - canvas: from full-bleed to rectangular middle (1000x1350 centered, radius 28, stroke, shadow, blurred bg)
   - type: from Khand only to multi-font (khand for Hindi talking, bebas for bold, didot for luxury)
   - pacing: from 30-40s to 7-15s (Reels length, 90 sec max)
   - voice: keep hi-IN-Swara for Hindi quotes, or add en option
2. antar/config.py: change default config path from antar.json to luxe.json
3. antar/panel/server.py & views.py: change "ANTAR" strings to "LUXE", title, banner
4. antar/render/render.py: make it call insta.py rectangular middle by default, or keep both and add flag --insta
5. antar/render/typekit.py: support multi-font, not Khand only
6. run.sh: echo "LUXE - One Click" not ANTAR
7. README_KALI.txt -> README_LUXE.txt
8. sfx_library/phonks/ folder: keep for user's trending phonks

KEEP SAME UI: panel at localhost:8787, same 9 tabs, same doctor, pipeline commands

ZIP: LUXE_STUDIO.zip - complete, open proper, ./run.sh works

## For PSYCHE (YT Faceless Psychology - DecoderYT style):

COPY: Same as LUXE - entire antar/ package, fonts, run files

EDIT:
1. config/psyche.json:
   - project.name: "PSYCHE"
   - lane: "practical-psychology" same as ANTAR lane B (being overlooked)
   - canvas: 1920x1080 or 1080x1920? For YT long-form: 1920x1080 landscape, for Shorts: 1080x1920 - support both
   - pacing: target 10-15 min (600-900 sec), not 30-40 sec - long-form like DecoderYT 14:32 avg
   - voice: hi-IN-Swara for Hindi, or en-IN-Neerja for English psychology
   - type: Khand for Hindi, plus Montserrat for English
   - thumbnail: bold white + black outline + shadow + shape (DecoderYT style)
2. antar/config.py: load psyche.json
3. panel titles: PSYCHE
4. render: full-bleed for long-form, plus Alight Motion style effects (curves, blend, Gaussian blur, shadows)
5. pipeline: different - longer script, more beats, 10-15 min voice
6. run.sh: "PSYCHE - One Click"
7. Add research: DECODERYT_ANALYSIS.md already

ZIP: PSYCHE_STUDIO.zip - complete, open proper

## Common for Both:

- Same UI: panel server, doctor, keys, vault, pipeline commands - user already knows ANTAR UI, so keep same but different name
- Same one-click: ./install.sh first time, ./run.sh every time
- Same structure: easy to edit from starting because it's copy of ANTAR
- Different name: folder, config, UI title, zip name, README

## Steps to Build:

1. Create /home/user/LUXE/ folder
2. Copy ANTAR/antar -> LUXE/antar
3. Copy assets, config, run files
4. Edit config/luxe.json, antar/config.py, panel/server.py, run.sh
5. Test: python run.py doctor, python run.py panel (should show LUXE)
6. Zip: LUXE_STUDIO.zip
7. Repeat for PSYCHE
8. Give both ZIPs
