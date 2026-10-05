ANTAR STUDIO - HOW TO START
===========================

1. Unzip ANTAR_STUDIO.zip into a folder.
2. Add your API keys to ANTAR/.env:
     PEXELS_KEY_1=<your pexels key>
     PEXELS_KEY_2=<optional second pexels key>
     GROQ_KEY_1=<your groq key>           (dead keys are kept, not deleted)
     GROQ_KEY_2=<optional second groq key>
   The first time you run `python run.py keys import` it will move them
   into ANTAR/config/state/keys.json. Dead keys stay listed there.
3. Run:
     python run.py keys test --all          (check the keys you just added)
     python run.py selftest                 (all 10 phases of tests, ~6 min)
     python run.py panel                    (operator UI in your browser)

The 51 MB vault/ folder is the footage library. Each clip is hashed and
tracked; a clip is never used more than twice across the whole library.

output/ already contains the records from the one finished render
(ANTAR_0001_lane-b-pilot). The MP4 itself is NOT in this zip - it lives in
ANTAR_VIDEOS.zip (separate deliverable, per the pack-and-delete rule).

WHAT IS HERE
------------
    antar/                source code (10 stages)
    tests/                selftest for every phase (229 pass, 1 skip)
    config/               antar.json + .env + state/
    assets/               fonts, palette, motion, voice samples
    vault/                51 MB footage library, hashed + tracked
    output/               audit trail of the one render
    PHASE1..10_REPORT.md  every phase's deliverable + score
    STATUS.md             project status, one page
    START_ANTAR.bat       Windows start (or use `python run.py` directly)

WHAT IS NOT HERE (intentional)
------------------------------
    .env                  your API keys
    config/state/keys.json your key store
    output/video/*.mp4    finished videos ship in ANTAR_VIDEOS.zip
    output/video/_parts   regenerated on next build
    __pycache__ / .pyc    regenerated on first import
    logs/antar.log        regenerated on every run