# PHASE 10 - PREMIUM FIX 2026-10-04

## User Report
- Caption "लेती" alone looks wired
- Same premium style, plain bg flash for seconds
- Passes all tests but looks cheap
- 11labs 402: Free users cannot use library voices via API -> fallback to Edge-TTS

## Root Causes

### 1. 11labs 402
- Default voice 21m00Tcm4TlvDq8ikWAM (Rachel) flagged as library for free tier
- Free tier can only use premade voices via API, not library/cloned
- Code tried only one voice, then fell back

### 2. Wired Captions
- chunk_words with max_words=1 created single word "लेती" alone
- "लेती", "है", "की" etc are stopwords that look wired alone
- Old gradient 237->108 = gray, not premium white
- No stroke, no shadow, no pill bg -> low contrast on footage

### 3. Plain BG Flash
- offline_write.py used object_hi="portrait-frame" which is NOT in OBJECTS dict
- resolve() fails -> query empty -> every beat becomes card (plain #12121A bg)
- Vault has 7 premium clips but never used when no API keys
- _services_with_keys returned UNKNOWN fake keys causing 25s timeout each

## Fixes

### 11labs - tts.py
- Added ELEVENLABS_FREE_FRIENDLY_VOICES chain of 7 premade voices
- Added _elevenlabs_fetch_usable_voice() to query /v1/voices for usable voice
- On 402, try next voice in chain + fetch usable voice
- Clear error message: "Free users cannot use library voices via API - upgrade or use Edge-TTS"
- Edge-TTS hi-IN-SwaraNeural is actually BETTER for Hindi (Hindi-native)

### Premium Captions - typekit.py
- POPUP_PAD 26->32, added STROKE 8, SHADOW 6
- HINDI_STOPWORDS_ALONE set: "लेती", "है", "की" etc never alone
- chunk_words now merges stopwords backward: "अकेलापन लेती" not "लेती" alone
- render_popup: premium white 255->235 (not gray 237->108)
- Added pill bg: semi-transparent black rounded rect (0,0,0,160) radius 24
- Added drop shadow: black offset 6px + GaussianBlur 3
- Added black stroke 8px for readability
- Hindi bump: 15% larger size for Devanagari

### Premium Clips - choose.py + plan.py + offline_write.py
- choose.py _score: prefer exact 1080x1920, penalize short clips, prefer higher megapixels
- grade.py presets: saturation 0.9->1.02-1.08, contrast 1.03->1.10-1.14 (more punchy)
- offline_write.py: use real Hindi objects from OBJECTS dict: "खिड़की", "कमरा", "कुर्सी" etc (10 objects)
  - Old: "portrait-frame" not in table -> 0 clips, 9 cards
  - New: all 9 beats have filmable objects -> 9 clips, 0 cards
- plan.py _services_with_keys: only return ALIVE keys, not UNKNOWN fake keys (prevents 25s hang)
- plan.py: vault fallback before AND after search - uses vault clips when no API keys
  - First fallback: if offline or not pairs, try vault
  - Second fallback: if search fails but vault has clips, use vault

## Results
- Offline pipeline: 0 clips 9 cards -> 9 clips 0 cards (no plain bg flash)
- Captions: "लेती" alone -> "अकेलापन लेती" merged, premium white with stroke+shadow+pill
- 11labs: clear reason for 402, chain of 7 voices tried before fallback
- Build: 34.68s video with 9 premium clips, 23MB, gamma 0.3-0.57, brightness 35-53

## Test
- chunk_words: "भीड़ में" + "अकेलापन लेती" (not "लेती" alone) ✓
- render_popup: 337x248 with pill+shadow+stroke ✓
- build_plan offline: 9 clips, 0 cards ✓
- build: 9 segs rendered, muxed to 22MB MP4 ✓
