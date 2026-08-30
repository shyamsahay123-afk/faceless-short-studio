# 🎬 Faceless AI Short Studio

One-click AI production pipeline for high-retention vertical Shorts:
**topic → script → voice → word-synced visuals → sound design → thumbnails → database.**
Every video uses the same locked channel identity (character bible + signature sound
+ accent color), so video #50 looks and sounds like video #1.

## 🚀 Run it

```bash
pip install -r requirements.txt
py -m streamlit run app.py
```

Keys (Pexels, Pixabay, ElevenLabs, HuggingFace, optional Pollinations) are entered
once in the sidebar and auto-saved to `.txt` files in this folder.

---

## 📈 1. Retention Re-Cut — the app learns from your viewers

YouTube Studio → your video → **Analytics → Average Percentage of Viewers → EXPORT (CSV)**.
In the app, under the script editor: upload that CSV → the engine finds where viewers
actually drop → **cuts that whole sentence out of the script** → re-render = shorter
video, no dead zone. It never cuts mid-sentence, the hook, or the CTA.

## 📋 2. Daily Autopilot — one command, one video, every day

```bash
py daily.py
```
Takes the next topic from **`queue.txt`** (one per line), drafts the script (auto-retrying
weak hooks), renders it with the locked channel style, saves to the database, runs the QC
report, and pushes the video + thumbnail to your GitHub **`videos`** repo.

Windows — make it automatic (run once):
```
schtasks /create /sc daily /st 09:00 /tn "FacelessDaily" /tr "py D:\2\myuse\daily.py"
```
Flags: `--topic "..."` (use this topic, queue untouched) · `--lang hi` (Hindi voice)
· `--no-publish`. Channel defaults live in **`daily_settings.json`** (edit freely).

## 🇮 3. Hindi (multilingual) variants

Write/paste the script in Hindi, pick a Hindi voice (**Hindi Male / Female**), render.
Everything else — backgrounds, cards, sound, thumbnails — is unchanged. Captions and
hook text auto-route to a Devanagari font (Noto Sans Devanagari is bundled). Same
pipeline works for any language edge-tts supports.

## 🔊 4. Signature Sound (audio identity)

Every video gets the same 0.5s stinger at 0.0s, same volume. Pro channels are
recognized by sound before the frame resolves — this is the ear's version of the
character bible. Deterministic: identical on every machine, every day.

## 🌑 GOONINGGNG MODE (the measured style of your reference channel)

One combination of settings reproduces the @GOONINGGNG look — every value below
was measured from `ref_video3.mp4`, not guessed:

| Setting | Choice | Why (measured) |
|---|---|---|
| Background Style | **Void Black** | ref: 66% of every frame is near-black |
| Pacing | **Deep Cosmic** | ref: 8-12 visuals per 65s, held 5-15s (we measured 8 cuts @ 4-6s) |
| Clip Mode | Full screen | ref shows full-frame cosmic footage, no windows |
| Caption Theme | **Typewriter** | ref: white 3-word fragments with a cursor bar |
| Hook | auto stack-contrast | ref: small gold line + HUGE white line |
| Grade | auto cosmic | ref: mean luminance 22/255, saturation 2% |
| B-roll | auto cosmos vocabulary | ref: only cosmos + clocks + brains, never people/cities |
| Sound | **AI SFX Director auto-picks** | ref: whoosh on transitions, ticks on clocks, riser→impact on the climax, sub-boom on the outro (max 6/video) |
| Outro | auto card + **daily code** | ref: logo outro with sub-bass boom |
| Watermark | bible `watermark` handle | ref: IG handle on every frame |
| Voice | Deep Narrator @ 0.92 | ref: slow, low delivery (median 132Hz, crisp) |

Plus the **Psychology Tricks** toggle (ON by default): one named secret per video,
rotating comment bait, a planted flaw every ~10th video — full spec in
`psychology_tricks.md`. The SFX director + tricks picks are logged in `studio.log`.

`daily_settings.json` ships pre-set to GOONINGGNG mode (void + cosmic +
typewriter). Set your `watermark` handle there (or in the app) and the autopilot
produces the style unattended.

## 🎧 4b. Reference SFX Pack (the sounds from your viral reference short)

`ref_video3.mp4` was dissected: 9 real SFX were detected, isolated and saved in
**`sfx_library/`** — the exact sounds the reference channel layers on its video:
energy flare, flare tail, tick tock, comet whoosh, clock hit, warp whoosh,
riser, climax impact, and the sub-bass outro boom. They're all in the
**"Meme Sound"** dropdown (first 3 = classic downloads, rest = the reference
pack, loaded instantly from the local folder — no download, no drift).

## 🎯 5. Hook Scorecard (pre-render gate)

While you edit the script, the app scores the hook 0–100 (length, number, "you",
curiosity gap, interrupt opener, no emoji, assertive ending) and tells you exactly
what to fix BEFORE you spend ~2.5 min rendering. `daily.py` uses the same scorer:
it regenerates weak hooks automatically (target ≥ 60).

## 🖼️ 6. Thumbnail Variants + Performance Log (the template that learns)

Every render produces **3 thumbnails** (different frame time, text position, signature
bar). After uploading, open the **Performance Log** expander in the app, paste the
video's CTR / views / avg retention from YouTube, and save. The channel remembers
which variant won — the next render makes that variant the primary.

## ✅ 7. QC Report

After each render: duration check, no dead-black frames, hook visible in the first
1.2s, no frozen footage, loudness ≈ -14 LUFS, no silent gaps, caption layer alive.
A 6-line ✅/⚠️ verdict before you upload anything.

---

## 🔧 The engine (how a video is built)

1. **Script** — psychology-triggered draft (curiosity gap, loss aversion, identity
   signaling…), fully editable in the UI.
2. **Voice** — ElevenLabs V3 presets (model chain V3 → V2 → turbo with loud fallback
   warnings) → edge-tts (word-synced) → gTTS, in that order. 7-step pro voice chain
   (HPF, EQ, compressor, de-esser, air, warmth, glue) + -14 LUFS normalization.
3. **Pro editor** — beat map + tension rhythm (cut-on-word, 2.5s hard cap,
   2-fast-then-slow breathing), climax = the card reveal moment.
4. **B-roll** — VTT-synced: the clip matches the word being SPOKEN right now
   (metaphor brain: 250+ abstract words → cinematic images). Pexels with hourly
   budget gate → auto-fallback to Pixabay → character-bible AI clips
   (HF + Pollinations, fixed seed = same look every clip).
5. **Elite text layer** — stacked hook, script beats, redacted curiosity card +
   reveal, stat card, before/after polarity card, arrow. SFX budget: max 5.
6. **Sound** — lofi bed, energy arc (build → peak at reveal → crash), voice-duck
   breathing, 40Hz sub-bass, word-synced captions (semantic color: red warnings,
   green gains, accent numbers), signature stinger.
7. **Output** — 720×1280 24fps mp4 + 3 thumbnails + word-level SRT + database row.

## 🗂️ Files

```
app.py               Streamlit UI (the whole studio)
video_engine.py      render pipeline (voice, broll, text, sound, thumbnails, QC)
style_engine.py      backgrounds, cards, arrows, fonts, SFX synthesis
pro_editor.py        beat map, rhythm, voice chain, music arc, loudness, QC
script_engine.py     script generator + hook scorecard
retention_engine.py  retention CSV parser + dip detector + script recutter
daily.py             CLI autopilot (queue → render → publish)
queue.txt            your daily topics (one per line)
daily_settings.json  locked channel defaults for the autopilot
db_manager.py        SQLite (channels, shorts, settings)
psychology_data.py   hook triggers library
youtube_engine.py    SEO copy pack generator
fonts/               Montserrat (latin) + Noto Sans Devanagari (Hindi) + DejaVu
performance_log.json CTR learning log (auto-created)
```

## 📁 Self-maintenance (automatic, nothing to do)

- **`studio.log`** — every render logs its stages (voice result, b-roll source,
  clip count, duration, QC report). It auto-truncates at ~1MB. When something
  behaves weird, this is the first file to open.
- **DB auto-backup** — after every render, `shorts.db` is copied to
  `shorts_backup_YYYYMMDD.db`; only the newest 3 snapshots are kept.

## 🧯 Known limits (honest list)

- Rendering needs ~2GB RAM headroom; batch mode forces a memory sweep between videos.
- Hindi text shaping is perfect where Pillow has raqm (Linux/Cloud); on Windows it's
  readable but the vowel marks sit slightly loose (no tofu, never).
- YouTube upload is manual (or via your own script) — `daily.py` publishes to the
  GitHub videos repo, which doubles as your backup.
- Pollinations without a key: ~1 image/15s + watermark. Add a free key in the sidebar
  to remove both.
