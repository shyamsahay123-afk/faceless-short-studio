# PROJECT AUDIT — FUTURE BUGS & PROBLEMS (prioritized)
Date: 2026-08-27
Method: read the actual current code (video_engine.py 2602 lines) + dependency
research (edge-tts 7.x, ElevenLabs v3, Pollinations limits) + 3-session bug history.

=============================================================================
STATUS: ALL P0+P1+P2 FIXES APPLIED & TESTED — 2026-08-29
=============================================================================
Every item below was fixed in code and verified by a LIVE full-pipeline render
(13s video, 152s render, word-synced SRT confirmed, 0 temp files left behind).

 P0 — ALL FIXED:
   [FIXED+VERIFIED] B1  edge-tts Communicate(boundary="WordBoundary") with
                        TypeError fallback. Live test on edge-tts 7.2.8: 19/19
                        single-word cues with real ms offsets (was sentence-level).
   [FIXED+VERIFIED] B4  gTTS fallback now builds a char-weighted word SRT;
                        srt=None can no longer happen. Plus fail-loud guard: if
                        ALL TTS engines die, the render stops with a clear error
                        instead of a cryptic ffmpeg crash.
   [FIXED+VERIFIED] B5  seg files tracked per render → closed then deleted after
                        the final write (0 leftovers after test render). Stale segs
                        >10min cleared at render start; startup sweep removes
                        seg_*/TEMP_MPY_*/voice_chain_input/temp_gen_*/_frame_tmp.
                        Thumbnail frame now in try/finally. Partial ffmpeg extractions
                        deleted on failure.
   [FIXED]           B6  requirements.txt: bounded pins (moviepy>=2,<3, edge-tts>=6.1,
                        <8, pillow<13, numpy<3 ...) + gtts ADDED (it was imported but
                        never declared — another silent death waiting).
 P1 — ALL FIXED:
   [FIXED+VERIFIED] B2  ELEVEN_MODEL_CHAIN: eleven_v3 → eleven_multilingual_v2 →
                        turbo. 401/403/404 = key problem → stops chain + clear message.
                        v2 settings auto-converted (speaker_boost→use_speaker_boost).
                        Every fallback prints loudly (no silent robotic voice).
   [FIXED]           B3  Optional Pollinations key (sk_/pk_) — sidebar field +
                        pollinations_key.txt + POLLINATIONS_KEY env. Key = no rate
                        limit + no watermark (sent as ?key= AND Bearer header).
   [FIXED+VERIFIED] F2  Pexels hourly budget gate (190/200 req/hr tracked). 429 or
                        cap → auto-switch to Pixabay (its own budget) for the hour.
   [FIXED]           B7  23 bare except: → 0. All replaced with specific types
                        (TypeError for font size-kwarg, Exception + print elsewhere).
 P2 — ALL FIXED:
   [FIXED]           B8  All data dirs + key files anchored to the app folder
                        (BASE_DIR/APP_DIR), CWD fallback kept for key files.
   [FIXED]           B9/O3  _force_delete with retry loop for Windows lock windows;
                        delete only AFTER clip.close(); startup sweep.
   [FIXED]           O1  prune_output_dirs(): newest 12 videos + newest 400 b-roll
                        clips kept, older deleted (startup + after each render).
   [FIXED]           O2  gc.collect() + prune after every render and between every
                        batch video (5-in-a-process OOM mitigation).
   [FIXED]           F4  HF circuit breaker: 2 consecutive failures → HF skipped
                        for 10 min (no more 40s dead attempts per clip).
   [FIXED]           F6/O4  ZIP is now key-free (keys never leave the user's PC).
 P3 — DONE (2026-08-29, round 2b):
   [DONE]            B7  error visibility (prints, fail-loud TTS guard).
   [DONE]            O4  auto-backup of shorts.db -> shorts_backup_YYYYMMDD.db
                        after every render, newest 3 kept (db_manager.backup_db).
   [DONE]            studio.log file logging (auto-truncates at ~1MB) + QC lines.
 BONUS (2026-08-29): ref_video3.mp4 sound analysis complete — 9 real SFX
   isolated into sfx_library/ and wired into the Meme Sound dropdown.

TEST EVIDENCE (2026-08-29):
   - py_compile clean on all 7 modules; 0 bare excepts project-wide.
   - generate_tts_audio live: 19 single-word SRT cues, real edge-tts timestamps.
   - Helper unit tests: sweep/force_delete/pexels-gate/pollinations-key/eleven-chain
     all pass; dead-key eleven call returns (None,None) without crashing.
   - Full create_hybrid_ai_video render: 152s, video+thumb+SRT+audio produced,
     seg temp files: 11 during render → 0 after. QC luminance sweep PASS.
   - Rendered frames checked: stacked hook (white+gold), grid+glow background,
     VTT-synced broll (spoken "brain" → neuron clip), red WARN-word captions.


=============================================================================
STATUS: FEATURE ROUND 2 (the growth loop) — 2026-08-29
=============================================================================
 1. retention_engine.py  — YouTube Studio retention CSV import -> dip detection
                            (hook-phase exempt, settle-aware baseline) -> whole-
                            SENTENCE recut of the script. UI section in app.py.
                            Tested: 30s synthetic curve, dip at 12-15s detected
                            at 15.7pt depth; correct sentence removed, hook +
                            CTA protected; 6 CSV layout variants parsed.
 2. script_engine.py     — script generator moved out of app.py (importable by
                            CLI) + HOOK SCORECARD (0-100, 7 checks). daily.py
                            auto-retries hooks below 60. Live badge in the UI.
                            Tested: strong hook 75 vs weak hook 35; retry gate
                            finds 75-point hooks; safety block intact.
 3. daily.py + queue.txt — CLI autopilot: queue -> script (score-gated) ->
                            render (locked style, daily_settings.json) -> DB ->
                            QC report -> git push to the videos repo -> log.
                            schtasks one-liner in README for daily schedule.
 4. Multilingual (Hindi) — hi-IN voices in the UI + daily --lang hi. CRITICAL
                            FONT BUG FOUND & FIXED: bundled DejaVuSans-Bold.ttf
                            was a CORRUPTED file (bad sfntVersion) AND DejaVu has
                            NO Devanagari glyphs -> tofu boxes in Hindi renders.
                            Fix: real Noto Sans Devanagari (Regular+Bold)
                            bundled; script-aware font router (Devanagari ->
                            Noto, other non-Latin -> DejaVu, latin -> Montserrat).
                            Tested: full Hindi render 85s, real Devanagari on
                            screen (shaping caveat in README: perfect where
                            Pillow has raqm; readable without, never tofu).
 5. Signature stinger   — deterministic 0.5s impact+shimmer+click at 0.0s,
                            0.5 x sfx_level, every video (audio identity).
 6. Thumbnail variants  — 3 per render (frame time / text y / bar position);
                            performance_log.json CTR learning: best-CTR variant
                            becomes the primary on the next render. UI expander
                            to paste CTR/views/avg-retention per video.
 7. QC report           — run_qc_report(): duration, luminance floor, hook
                            visible in 1.2s, frozen-frame check, loudness
                            ~-14 LUFS, silent gaps >0.8s, caption cue count.
                            Shown in the app after render + printed by daily.py.

KNOWN LIMITS (honest): Hindi shaping without raqm (Windows) = readable but
marks sit loose; YouTube upload stays manual (daily.py pushes to the GitHub
videos repo instead); thumbnail CTR learning is manual-paste (no OAuth).

=============================================================================

=============================================================================
ORIGINAL AUDIT (kept for reference)
=============================================================================


=============================================================================
A. CONFIRMED LATENT BUGS IN CURRENT CODE (will bite)
=============================================================================

[MED] B1 — edge-tts 7.x: captions are SENTENCE-APPROXIMATE, not word-synced.
  root: edge-tts 7.2+ changed the DEFAULT boundary from WordBoundary to
        SentenceBoundary. Our code only feeds SubMaker on WordBoundary events, so in
        7.x SubMaker is never fed -> word_srt empty -> captions fall back to
        "distribute the sentence's words by character weight" = APPROXIMATE timing
        (works, but words can drift a few hundred ms off the voice).
  fix: pass boundary="WordBoundary" to Communicate (edge-tts 7.x supports the
       boundary kwarg) to get TRUE word-level timestamps -> perfectly synced captions.
       Keep the sentence fallback for older edge-tts versions.

[HIGH] B2 — ElevenLabs: model_id "eleven_v3" hardcoded; v3 API may need a paid plan;
       word-timestamps API unused.
  root: `eleven_v3` went GA March 2026 but "API access — contact sales / paid tier".
        If the user's key is on a free/legacy plan, eleven_v3 returns 401/400/404 →
        SILENT fallback to robotic edge-tts (no warning shown to user).
        Also even on success we write an ESTIMATED srt (char-proportional), not
        ElevenLabs' real word timestamps (v3 Timing API returns exact word/char
        timestamps for $0.10/1k chars) → captions drift.
  fix: make model configurable + detect 401/400/404 → show a clear "your key can't
       access v3, using fallback voice" message (never silent). Optionally call the
       v3 Timing endpoint for exact word timestamps (or use output_format with
       word-level timestamps) so captions are perfectly synced.

[HIGH] B3 — Pollinations keyless = rate-limited (~1 req/15s) + WATERMARKED + no SLA.
  root: keyless Pollinations is rate-limited to ~1 image/15s and WATERMARKED, no
        uptime SLA. Batch mode (5 videos × ~10 clips = 50 images) will HURT the rate
        limit → failures/timeouts mid-batch. Watermark = visible brand on images.
  fix: add an OPTIONAL Pollinations secret key (sk_) field in the app key settings.
        A sk_ key = NO rate limit + NO watermark (server-side). Fallback chain:
        Pollinations(sk_ or keyless) → Pexels → solid card. Add a small delay/queue
        between keyless requests to respect the rate limit.

[MED] B4 — gTTS fallback returns srt=None → ENTIRE caption/beat/SFX layer silently dies.
  root: line 1531 `return audio_path, None`. If ElevenLabs AND edge-tts both fail,
        gTTS makes audio but srt_path=None → parse_vtt(None)=[] → NO captions, NO
        beats, NO SFX sync — and it fails SILENTLY (user gets a video with no captions
        and no idea why).
  fix: on gTTS fallback, GENERATE a fallback srt (even-split words over audio duration)
       instead of returning None. Never return a None srt.

[MED] B5 — TEMP FILE LEAK (disk accumulates every render).
  root: `seg_{pid}_{ts}_{idx}.mp4` (per-clip segment, unique name) is created in
        add_broll and NEVER deleted. `voice_chain_input.wav` (when elevenlabs fails
        and we convert), MoviePy's `TEMP_MPY_wvf_snd.mp3`, and the thumbnail
        `*_frame_tmp.jpg` can also linger on crash. Each 30s video = ~15-20 seg files
        that never get removed → over days/weeks the disk fills.
  fix: wrap segment + temp creation in try/finally with os.remove(); add a
       cleanup function that sweeps seg_*.mp4 / TEMP_MPY* / temp_gen_* / *_frame_tmp
       at the START of each render (delete stale files from crashed runs).

[MED] B6 — requirements.txt UNPINNED → version drift breaks the build.
  root: `moviepy>=2.0`, `edge-tts>=7.0`, etc. are lower-bounds, not pins. edge-tts
        ALREADY changed its API in 7.x (see B1). A future `pip install -r
        requirements.txt` on a fresh PC could pull a breaking version → silent breakage.
  fix: PIN exact versions that are known-good: e.g. moviepy==2.2.x, edge-tts==7.x.y,
        moviepy's deps, etc. Freeze the exact versions that render correctly.

[LOW-MED] B7 — 23 bare `except:` clauses swallow errors and hide real bugs.
  root: `except:` (bare) across video_engine.py/app.py hides the actual exception,
        so a real bug silently degrades instead of surfacing. Makes future debugging
        much harder (this is why the audio bug was hard to find).
  fix: replace `except:` with specific exception types + log the error (print/log with
       the exception) so failures are visible, not silent.

[LOW] B8 — CWD-relative paths (AUDIO_DIR, B_ROLL_DIR, VIDEO_DIR are relative).
  root: AUDIO_DIR="audio_clips" etc. are relative to the CURRENT WORKING DIRECTORY.
        If the user runs `streamlit run` from a different folder than myuse/, the
        temp/output files land in the wrong place and the app "loses" its files.
  fix: anchor all dirs to the script's own directory:
       BASE = os.path.dirname(os.path.abspath(__file__)); AUDIO_DIR=os.path.join(BASE,"audio_clips")

[LOW] B9 — MoviePy temp audio (TEMP_MPY_wvf_snd.mp3) + clip file locks on Windows.
  root: MoviePy writes a temp audio file per render and can leave it LOCKED on Windows
        if a render crashes; Windows file locks can block the next render or the ZIP.
  fix: cleanup in finally + a "delete leftover TEMP_MPY* at startup" sweep.

=============================================================================
B. FUTURE FAILURE MODES (external dependencies)
=============================================================================

[MED-HIGH] F1 — Pollinations keyless rate limit + watermark + no SLA (see B3).
[MED] F2 — Pexels free tier = 200 requests/hour. Batch (50 images/video-set) is fine
           once, but repeated batch runs hit the hourly cap → 429 errors.
           Fix: clip cache (done), add a short cooldown + graceful "rate limited,
           retry in X" message, and Pixabay as automatic fallback.
[MED] F3 — ElevenLabs key: credit exhaustion (402) or key expiration (401) → silent
           fallback to robotic edge-tts. Fix: surface a clear warning, never silent.
[LOW] F4 — HuggingFace credits are DEPLETED (402). The "huggingface" b_roll_source
           path wastes a ~40s timeout then falls back. Fix: make HF optional/skippable
           (off by default) so it doesn't waste 40s per clip.
[LOW] F5 — Pollinations/HF model availability changes (no SLA). Fix: multi-provider
           fallback chain + a clear "provider down, using fallback" message.
[MED] F6 — Windows Defender/antivirus quarantines the ZIP (it contains API keys).
           Fix: ship the ZIP WITHOUT the key .txt files; have the user re-add keys in
           the app UI (they're already in the app's key settings), or deliver keys
           separately.

=============================================================================
C. OPERATIONAL / INFRASTRUCTURE
=============================================================================

[MED] O1 — DISK ACCUMULATION: temp seg files (B5) + b_roll_library/ (cached clips grow
           unbounded) + video_output/ (finished videos grow unbounded). Over weeks the
           D: drive fills. Fix: temp cleanup (B5) + optional "keep last N outputs"
           pruning + a "clean cache" button in the app.
[MED] O2 — MEMORY/OOM in BATCH mode: 5 videos render in the SAME Python process;
           memory + temp files accumulate between videos → OOM risk on low-RAM PCs.
           Fix: render each batch item and aggressively close/cleanup between items,
           or run each video in a fresh subprocess.
[LOW] O3 — Windows file locks (B9) can block re-renders after a crash.
[MED] O4 — DEPLOYMENT: antivirus quarantines the key-bearing ZIP (F6). Fix: key-free ZIP.

=============================================================================
D. PRIORITIZED FIX LIST (order to fix)
=============================================================================
 P0 (breaks output silently / data loss):
   B4  gTTS srt=None → generate fallback srt (silent caption death)
   B1  edge-tts word boundaries → real word-synced captions
   B5  temp file leak → cleanup (disk fill)
   B6  pin requirements versions (reproducibility)
 P1 (degrades quality / wastes time):
   B2  ElevenLabs v3 → clear fallback warning + word timestamps
   B3  Pollinations sk_ key option (rate limit + watermark)
   F2  Pexels rate-limit cooldown + Pixabay fallback
   B7  replace bare except: with logged specific exceptions
 P2 (robustness):
   B8  anchor paths to script dir (CWD-independent)
   B9/O3 temp file lock cleanup on startup
   O1  cache/old-output pruning + "clean cache" button
   O2  batch per-video cleanup (or subprocess per video)
   F4  make HF optional (off by default)
   F6  key-free ZIP (keys entered in UI only)
 P3 (nice-to-have):
   B7  full logging to a file (studio.log) for debuggability
   O4  optional auto-backup of shorts.db

=============================================================================
E. WHAT IS ALREADY SAFE (no action)
=============================================================================
- MoviePy 2.x API usage (resized/cropped/with_position) is correct for 2.x
- Voice presets (V3 settings) are correct values
- Audio mix (arc + duck + sub-bass) is correct
- SFX safe-wav loader is correct (no "images do not match" bug)
- Thumbnail generator size-mismatch is fixed
- Subject-anchor crop is correct
- B-roll segment extraction (memory-safe) is correct
