# ANTAR — WHERE THE PROJECT IS
_(written 2026-09-28, after Phase 10 + the learn loop)_

---

## 1. What ANTAR is

A **Hindi YouTube Shorts studio that runs itself**, built from scratch — no
line of code carried from any earlier version.

- **10 stages, one after another:** topic → title → script → voice → words →
  picture → build → check → score → details/publish.
- **It writes in Hindi**, talks to one person (तुम), dark luxury tone, no memes.
- **Everything is free:** Edge-TTS for the voice, Pexels/Pixabay for footage,
  cloud models on free keys. No subscriptions, nothing paid, ever.
- **It checks itself** before anything can be uploaded — 7 blocking rules,
  11 warnings, and a score out of 100. Under 85 it does not ship.
- **It never repeats itself:** 8 fixed values, 11 that rotate every video,
  no clip used more than twice, lookalikes counted as repeats.

---

## 2. Where the build stands

| phase | what it does | state |
|---|---|---|
| 1 · Foundation | config, vault, keys, single instance | **done** · 31 tests · 93/100 |
| 2 · Words | topics, Hindi writer, structure | **done** · 27 tests · 91/100 |
| 3 · Voice | Edge-TTS, word timings, mastered audio | **done** · 21 tests · 91/100 |
| 4 · Picture | every beat gets a clip or a text card | **done** · 21 tests · 92/100 |
| 5 · Build | the finished 1080×1920 MP4 | **done** · 27 tests · 92/100 |
| 6 · Check | 7 blocking + 11 warnings + the scorecard | **done** · 22 tests · 91/100 |
| 7 · Details | titles, description, tags, pinned comment, thumbnail | **done** · 18 tests · 92/100 |
| 8 · Panel | the operator UI: nine tabs, one button, the live console | **done** · 20 tests · 90/100 |
| 9 · Proof | real thumbnails + every numbered test-plan item, with numbers | **done** · 22 tests · 91/100 |
| 10 · Learn | CSV in -> rotation ranking -> next topic brief -> Distinctness closed | **done** · 20 tests · 90/100 |

**Tests: 229 passed, 1 skipped, across all ten phases** — `python run.py selftest`

**Tests: 228 passed, 1 skipped, across all ten phases** — `python run.py selftest`

The one skip reads the finished render to prove every blocking check passes on
it. That video is packed in `/home/user/ANTAR_VIDEOS.zip` and deleted from the
workshop, so the test says it did not run rather than passing quietly. Extract
`ANTAR_0001_lane-b-pilot.mp4` into `output/video/` and it runs for real.

### There is a finished video

`ANTAR_0001_lane-b-pilot.mp4` — 34.95s, 1080×1920, 30fps, 18MB, voice at
−14.5 LUFS. **It now lives in `/home/user/ANTAR_VIDEOS.zip`, not in the
workshop** — videos are delivered as a zip and deleted, as instructed. Its
check record and its build sheet stay in `output/video/`.

Its own check run, with the details stage finished:

**16 pass · 2 warn · 0 fail** · score **88/100 measured, 5 withheld**
(5 for Distinctness — Phase 10 compares videos with each other, so it is
withheld rather than invented).

### The details for that video

```
TITLE   लोग इग्नोर क्यों करते हैं और अकेलेपन का सच     100/100
        target 80 · gate 70 · 42 characters · live harvested phrase, word for word
TAGS    15, no hashtags · DESCRIPTION 3 hashtags · PINNED COMMENT 20 words
FILE    output/details/ANTAR_0001_lane-b-pilot_details.json
```

The title score wiring defect is fixed: the check suite and the generator now
score against the same phrase list, so the gate reads 100 instead of 65.

The 2 warnings, in plain words:
1. the loop seam on the shipped file is 0.0800s against a 0.08 limit — the
   master audio is 0.050s, the extra ~20ms is padding the AAC encoder adds;
2. that script has no open question in it, so there is no micro-loop.

---

## 3. The key situation (fixed this round)

**What you saw:** keys for services ANTAR had no test for — deepgram and
others — showing up as unrecognised.

**What it is now:**

| | |
|---|---|
| services ANTAR can test | **16** — pexels, pixabay, groq, gemini, deepgram, openai, anthropic, elevenlabs, huggingface, openrouter, together, replicate, stability, removebg, serpapi, youtube |
| how each is tested | **1–3 different ways**, and the API's own words are printed next to the result |
| where each key is filed | automatically, from your `.env` — `DEEPGRAM_API_KEY` becomes a deepgram key, `YOUTUBE_DATA_API_KEY` a youtube key, and so on |
| a key with no check yet | **kept, never deleted, never called dead** — the run says which services do have checks |

**Genuine bug this round also fixed:** Google's APIs answer a bad key with
**400**, not 401, and say "API key not valid". The checker used to read that as
"unknown". Now a refusal carrying the API's own words counts, whatever the
status code — so a YouTube key is reported correctly.

Every check was verified live: twelve services were asked with a deliberately
invalid key and eleven answered "dead" with their own message; the twelfth
(youtube) exposed the 400 bug, which is now fixed.

### On your Windows machine

```
python run.py keys test --all
```

`--all` matters: it asks the keys that were written off, instead of skipping
them. You will get a table like:

```
service  key                    verdict    what the API said
pexels   USAgWI...VwdT          ALIVE      3 of 3 routes answered
         route videos 200       1 video(s) 2160x4096
deepgram ...
```

Nothing needs remaking. Keys are never deleted, and a key cannot be called
dead by a status code alone any more.

---

## 4. What happens next

**Phase 8 — Panel.** The window you actually look at: run the check-ups from
it, read the title and the description it wrote, fix the thumbnail by hand in
the SEO tab. Built fresh from the spec, same workflow as before.

Then: **9 Proof** (the real thumbnail, the final scorecard with numbers)
→ **10 Learn** (the analytics loop that tells the next topic what worked).

The upload unlock (85) still cannot be judged on its own, because 5 of the 100
points come from Distinctness — comparing this video with the ones before it —
and that belongs to Phase 10. 88/100 is what is measured today.

**Two things still open from earlier phases**, both named honestly:
1. two beats carry footage that does not match the script's fact (the
   airplane-window beat) — a picture-stage query to tighten;
2. ANTAR has never been run on Windows end to end.

---

## 5. Housekeeping done this round

| | |
|---|---|
| workspace | **209 MB → 121 MB** |
| removed | every `__pycache__`, `.pyc`, `.pytest_cache`, an 88 MB pip cache, test fixtures and scratch renders |
| kept | the vault (51 MB of footage), the finished video, all six phase reports, the archives of your old projects (13 MB — say the word and those go too) |
