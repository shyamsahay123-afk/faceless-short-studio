# THE EDITING SKILLS BIBLE — 12 PIECES, PRO STANDARDS + EXACT SPECS
Research date: 2026-08-27 | Status: RESEARCH ONLY (no code yet)
Purpose: break the whole video pipeline into small pieces, each with the pro standard
measured from 2026 research, the app's current state, and the exact spec for the fix.

=============================================================================
PIECE 1 — DEEP PSYCHOLOGY (SCRIPT LAYER)  ✅ DONE
=============================================================================
Status: DONE — script generator already has: but/therefore spine, breadcrumbs,
curiosity loops, sound-drop tags, save-trigger lists, loop closure.
No changes needed.

=============================================================================
PIECE 2 — AI SCRIPT QUALITY  ✅ DONE (minor)
=============================================================================
Status: DONE — attract-word hooks are in (numbers, secrets, self-reference).
Minor spec: scripts must be CONVERSATIONAL (research: conversational writing +
intentional punctuation = more natural AI voice). Keep sentences short.
No structural changes needed.

=============================================================================
PIECE 3 — TEXT: FONT, COLOR, STYLE  ⚠️ NEEDS LOCKING (the "choose" part)
=============================================================================
PRO STANDARD (2026 caption research — blitzcut, vsubtitle, madegooddesigns, opus):
- FONT: ONE family for the whole channel, bold sans-serif.
  Pro picks: Montserrat Bold, Anton, Poppins Bold, Roboto (YouTube's own caption font).
  NEVER thin weights, never serif in captions, never italics.
- COLOR: white = primary (90% of words). Yellow = high-energy accent (power words).
  NEVER red/green/blue for caption words (contrast + colorblind issues).
  Accent color for power words only (brain/secret/wrong/money/numbers).
- STROKE: 2-4px black outline (current app uses 5-6 = slightly thick; spec 3-4px).
- SIZE at 720x1280 (our render size): 45-55px (pro: 60-75px at 1080p; scale to 720).
  Hard cap 60px. Current 55px = OK, keep 50-55.
- LINE LENGTH: max 42 chars/line (Netflix standard), max 2 lines.
- POSITION: 65-75% down from top (current = 80% = slightly LOW; spec 0.70-0.72).
  Must clear: bottom 300px dead zone (at 1080p; at 1280h = ~200px), right 48px.
- DISPLAY: each caption block 1.5-3s; reading speed ≤20 chars/sec.
  Sync captions 0.1-0.3s BEFORE the word is spoken (not after).
- STYLE (choose ONE and lock):
  Option A "HORMOZI" (current default): word-by-word, yellow power words, bounce. HIGH ENERGY.
  Option B "CINEMATIC BLOCK" (reference #3 style): 2-4 word phrases, white, no bounce,
    clean. CALM/PREMIUM.
  SPEC: make BOTH selectable per render (both already exist in code; just expose in UI).

SPEC FOR APP:
- Lock font: Montserrat Bold (already bundled ✓)
- Stroke 5→3px, position 0.80→0.72, size 50-55
- Caption style picker: Word-Pop (energy) / Block (cinematic)
- Caption sync offset: -0.15s (captions lead the voice slightly)

=============================================================================
PIECE 4 — VISUAL CONSISTENCY (the "not fixed, random pexels" complaint)  ❌ THE BIG ONE
=============================================================================
PRO STANDARD (adwave, vivideo, flick.art, genra, captionplug, 8-month faceless reddit):
- "A template is not a literal template you fill. It is a SET OF VISUAL RULES:
  this is my palette, my typography, my lighting style, my composition."
- CONSISTENCY TEST: freeze a mid-frame from 3 of your videos. If a stranger can't
  tell they're from the same channel → your style is drifting.
- THE ALGORITHM PENALTY: "audiences notice repetitive layouts after 10-15 videos.
  The algorithm detects template-IDENTICAL patterns and suppresses as low-effort AI
  content." → consistency = same STYLE RULES, different SCENES (not identical frames).
- AI CHARACTER CONSISTENCY (2026 standard):
  * "Even identical text prompts produce slightly different results every time" = IDENTITY DRIFT
  * Fix = CHARACTER REFERENCE: 3-5 reference images (front, 3/4, profile, close-up,
    neutral light, clean bg, SAME OUTFIT) → use as reference for ALL generations
  * "Prompt stability alone rarely survives" — reference image is the standard
  * PRACTICAL FOR US (Pollinations): FIXED SEED + FIXED character description
    in every prompt = same character every time. (Current app: random seed every
    image = THIS is why our visuals drift video to video.)
- BATCH WORKFLOW (the money workflow): "write all scripts for the week, then
  generate all videos, then all QC, then export" — assembly-line, not per-video.
- COPYRIGHT: Pexels = 100% free for commercial use, no attribution. Pixabay = same.
  So "free OR copyright" worry is GONE — both are safe. Keep using them.

SPEC FOR APP:
- CHARACTER BIBLE file: `character_bible.json` = {name, seed, description,
  outfit, lighting, expressions[]} — user defines ONCE in the app UI, locked forever
- Every AI image prompt = bible description + scene + FIXED seed (seed + small
  increment per video so it's not identical but stays consistent)
- B-ROLL SET: curated rotation — generate/download 24-30 clips ONCE per niche,
  store in b_roll_library, rotate through them (same 24 clips in different order
  + different segments = consistency without template-identical penalty)
- STYLE LOCK: bg style + accent + font + grade are channel settings (saved once),
  not per-video choices

=============================================================================
PIECE 5 — FULL AUTOMATION ("AI doesn't generate automatically, switches to pexels")  ❌
=============================================================================
WHY IT HAPPENS (diagnosis):
- "True AI Generated" = Hugging Face first → HF credits depleted (402 error) →
  fallback chain → Pexels. The user SEES pexels and thinks "it switched".
- HF included credits are used up (verified: 402 Payment Required).

PRO STANDARD (how real AI video tools work — adwave/wavemaker, clippie, invideo):
- Generation is PRIMARY with fallback chain, NOT pexels-primary
- "Multi-provider fallback so generation doesn't stall"
- Subject consistency across the pipeline

SPEC FOR APP:
- NEW AUTOMATION MODE: "Auto" = Pollinations (keyless, always works, FLUX) as the
  PRIMARY AI generator (no credits to deplete), HF as secondary, Pexels as last resort
- The app should generate the ENTIRE video from a topic with ONE click:
  script → voice (V3 settings) → character-bible visuals → auto-assembly
- No user choices needed in automation mode (all from channel bible)
- Progress shown in the 2-line console (already built)

=============================================================================
PIECE 6 — CUTTING, CLIPS, RATIO  ⚠️ NEEDS REFINEMENT
=============================================================================
PRO STANDARD (pro editor brain research, already built, needs tuning):
- Cut rhythm: tension-based 1.0-2.4s, cut ON the spoken word (built ✓)
- Breathing pattern: 2 fast cuts → 1 slow (built ✓)
- HARD CAP 2.5s (built ✓)
- RATIO (the new complaint): clips are 16:9 → center-crop to 9:16 LOSTS THE SUBJECT
  (faces cut off, objects clipped).
  PRO FIX:
  * Prefer PORTRAIT (9:16) clips from Pexels (orientation=portrait — already
    requested ✓ but pexels results vary)
  * SMART CROP: detect the subject region (face detection or motion centroid) and
    crop AROUND it, not dead-center
  * ZOOM PUNCH 6% (built ✓)
- SPEC:
  * Keep orientation=portrait (✓)
  * Add subject-aware crop: use the clip's brightest/most-saturated 60% center band
    as crop anchor (cheap heuristic, no ML) — or simple: crop with subject at
    vertical center (subjects in pexels portrait clips are centered)
  * If a clip's subject is clearly off-center (top/bottom 20%), nudge crop anchor

=============================================================================
PIECE 7 — VOICE: NOT ROBOTIC, USE TONES  ❌ THE FIXABLE ROBOT
=============================================================================
WHY IT SOUNDS LIKE A ROBOT (diagnosis from code):
- App uses model "eleven_monolingual_v1" = THE MOST ROBOTIC model (V1, 2022)
- Settings: stability 0.45 (OK), similarity 0.75 (OK), but MISSING:
  style_exaggeration (currently 0 = flat), speaker_boost (currently OFF = weak)
- Edge-TTS fallback = ALWAYS robotic (Microsoft neural TTS, no tone control)

PRO STANDARD (michydev 2026 guide, recharm, zyncai, reddit — consensus):
- MODEL: **V3 (eleven_v3)** for narration = conversational, emotional. V2 for stable.
- STABILITY: 30-45% (high = monotone robot; low = expressive)
- SIMILARITY BOOST: 75-80%
- STYLE EXAGGERATION: 15-25% for monologue narration (THIS adds the "tone")
- SPEAKER BOOST: ON (stronger, clearer presence)
- SPEED: 0.95-1.1 (0.96 = natural narrator cadence)
- OPTIMIZATION: quality mode
- VOICE CHOICE > settings: test multiple voices with the SAME sentence first
- SCRIPT INFLUENCES: conversational writing + intentional punctuation = natural
- TONE = the combination of model + stability + style + voice choice

SPEC FOR APP:
- Switch model eleven_monolingual_v1 → **eleven_v3**
- Settings: stability 0.35, similarity 0.78, style_exaggeration 0.20,
  speaker_boost true, speed 0.98
- VOICE PICKER: 3-4 pre-picked voices per vibe (deep male narrator, energetic male,
  warm female, calm female) — user picks ONCE (goes into channel bible)
- Keep edge-tts fallback but mark it clearly as "basic" (so user knows when the
  premium voice failed)

=============================================================================
PIECE 8 — MEMES + STICKERS  ⚠️ ARRANGEMENT
=============================================================================
PRO STANDARD:
- Stickers are SUPPORT, never the star (1-2 on screen max)
- "Sticker at THE moment + SFX behind it" = the unit (they arrive together)
- Micro-memes: 1 per video max for premium niches (psychology/money)
- The sticker+SFX+text must land on the SAME beat

SPEC FOR APP (already built, needs arrangement lock):
- Micro-meme sticker: max 1 per video, at the [MICRO_MEME:] tag, WITH a pop SFX
  at the exact same second (built ✓)
- Save-trigger card: max 1, at [SAVE_TRIGGER_LIST:] (built ✓)
- NO stickers in the first 3s (hook zone stays clean)
- Stickers never overlap the caption zone (bottom 25%)

=============================================================================
PIECE 9 — SOUND: FADES, WOOOPS, SFX ARRANGEMENT  ⚠️ THE "MAYBE WRONG" PART
=============================================================================
PRO STANDARD (add.app, epidemicsound, youtubesfx — consensus):
- HIERARCHY (loudest→quietest): VOICE (-6 to -12dB) > SFX (-15 to -18dB) > MUSIC
- MUSIC LEVEL: 12-18dB BELOW voice during speech
- FADE IN: music 0.5s fade-in (voice starts clean first 0.3s)
- FADE OUT: last 1.5s fade (never dead stop)
- SFX PLACEMENT (the "arrangement" the user said "maybe wrong"):
  * HIT: ON the cut/reveal — "keep transient clean, leave room for dialogue"
  * RISER: builds INTO a reveal — "fade before the impact so the hit can breathe"
  * WOOH: camera moves/fast transitions — "match speed+direction to picture"
  * "The best dramatic sound is not always the loudest. A short hit landing
    EXACTLY on the cut hits harder than a long riser."
  * SFX "used dietetically, to create a bond with KEY visual moments"
- THE 5-SFX MAP (already built, this is the LOCKED arrangement):
  1. Soft hit @ 0.42s (on the hook)
  2. Whoosh @ card appearance
  3. Ding+Impact @ reveal (the ONE big moment)
  4. Soft hit @ end (loop line)
  + max 3 power-word ticks (built ✓)
- NO whoosh per cut (the 18-whoosh video = the bug, now fixed)

SPEC FOR APP (locked arrangement — already built, just verify in UI):
- The 5-event map above is the ONLY arrangement. Expose a "SFX level" slider
  (0-100%) so user can dial the whole SFX layer up/down as one knob.

=============================================================================
PIECE 10 — FILTERS / COLOR GRADE  ⚠️ CONSISTENCY
=============================================================================
PRO STANDARD (markstudios 2026, our earlier research):
- 3-layer grade: primary correction (match all clips to same exposure) →
  style grade (the look) → platform compensation
- PRIMARY CORRECTION is the consistency key: every clip must land at the SAME
  exposure/balance BEFORE the style is applied (else clips jump brightness)
- STYLE GRADE: one LUT, locked, every clip (dark premium: mid-gray darken +
  contrast 1.10 + saturation 1.15)
- PLATFORM COMP: +15-20% contrast/saturation for Shorts compression crush
- CONSISTENCY: "freeze 3 mid-frames, same look or it fails"

SPEC FOR APP (partly built):
- Per-clip exposure match: BUILT (exposure_gain_for_frames ✓)
- Locked style grade: BUILT (grade_frame ✓)
- MISSING: the grade must be the SAME every render (it is — it's code, not random)
  → just verify the LUT never changes between renders (it doesn't) ✓
- SPEC: keep grade locked in code, NO per-video grade randomness (current ✓)

=============================================================================
PIECE 11 — UPLOAD PATTERN ("same pattern, same visuals, like the video that
attracts me" — the piece you forgot to tell)  ❌ NOT BUILT YET
=============================================================================
PRO STANDARD (youtubethumbnailgrabs, azbigmedia, captionplug):
- "The template is a set of VISUAL RULES, not a literal template"
- RECOGNITION: "subscribers recognize it as yours BEFORE reading a word"
- FACELESS THUMBNAIL SUBSTITUTES (no face): hands-in-action, silhouette,
  BIG TYPOGRAPHY, before/after split, big number
- THUMBNAIL TEMPLATE: same palette, same font, same layout, same composition —
  every thumbnail. 1280x720 JPG 90%. Text <5 words.
- YouTube has NATIVE THUMBNAIL A/B TESTING (test 2-3 variants)
- POSTING PATTERN: consistent time daily (the algorithm learns the audience window)
- TITLE PATTERN: same formula (number + curiosity: "The 3-Second Rule That...")
- TAG PATTERN: same core tags + topic tags

SPEC FOR APP (NEW PIECE — not built yet):
- THUMBNAIL GENERATOR: auto-generates a 1280x720 thumbnail FROM THE VIDEO:
  frame at 1s + hook text (2-3 words, channel font/accent) + consistent layout
- THUMBNAIL TEMPLATE LOCK: layout+font+palette from channel bible
- TITLE PATTERN: hook formula template with the topic plugged in
- POSTING TIME: user sets one time, app remembers (or they post manually)
- A/B: generate 2 thumbnail variants, user picks (or uses YT native test)

=============================================================================
PIECE 12 — THE FULL AUTOMATED PIPELINE (the assembly line)  ❌ NOT BUILT YET
=============================================================================
PRO STANDARD (adwave batch workflow):
"Lock a template (same voice, intro, music mood, aspect) → write all scripts →
generate all videos → all QC → export batch. Video #50 looks as polished as #1."

SPEC FOR APP (the end state):
ONE-CLICK MODE: topic in → video out.
Pipeline: topic → [script generator (piece 1)] → [voice V3 (piece 7)] →
[character-bible visuals (piece 4)] → [VTT-synced cuts (piece 6)] →
[locked grade (piece 10)] → [5-SFX map (piece 9)] → [captions (piece 3)] →
[thumbnail (piece 11)] → MP4 + thumbnail.
BATCH MODE: 5 topics in → 5 videos + 5 thumbnails out (assembly line).

=============================================================================
PRIORITY ORDER (smallest → biggest impact)
=============================================================================
1. VOICE V3 + tones (piece 7) — 30 min, biggest "robot" fix
2. CAPTION LOCK (piece 3) — 20 min (stroke/position/size/style picker)
3. CHARACTER BIBLE + fixed seed (piece 4) — 1 hr, kills visual drift
4. AUTOMATION MODE (piece 5) — Pollinations primary, one-click — 2 hr
5. THUMBNAIL GENERATOR (piece 11) — 1 hr, the "same pattern on upload" piece
6. CROP ANCHOR (piece 6) — 30 min
7. SFX LEVEL KNOB (piece 9) — 15 min
8. BATCH MODE (piece 12) — 1 hr

Total: ~6-8 hours of building across 2-3 sessions. Every piece is small and
independently testable. Nothing needs to be rebuilt — everything extends what
already works.
