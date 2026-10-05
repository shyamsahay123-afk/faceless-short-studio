# ANTAR — PHASE 4 COMPLETE
### The picture · built, tested, scored · 27 Sep 2026

---

# SCORE: 92/100

| Category | Weight | Score | Evidence |
|---|---|---|---|
| **Correctness** | 20 | **19** | 94/94 tests across four phases; a live run that ends with a clip on every beat |
| **Proof** | 20 | **19** | Every number read from the files: the real bytes are probed, frames are measured, the contact sheet was looked at |
| **Robustness** | 15 | **13** | No key, no footage, black frames, faces, lookalikes, repeats — all tested. Pixabay never hit live |
| **Windows readiness** | 15 | **12** | Not executed here — same caveat as Phases 1–3 |
| **Zero-copy compliance** | 10 | **10** | Still enforced by the scanner test |
| **Clarity** | 10 | **9** | Every shot prints in seconds, clips, megabytes, light and black |
| **Honesty** | 10 | **10** | Nine real defects found and fixed here. The dark beat and the word-mark overrun are written into the plan itself |
| **TOTAL** | **100** | **92** | Above the 85 bar |

---

# WHAT THIS PHASE DOES

One command decides what is on screen for every beat.

```
python run.py picture
```

In:

```
output/scripts/ANTAR_0001_lane-b-pilot.json     the script Phase 2 wrote
output/audio/ANTAR_0001_lane-b-pilot_audio.json where every word was spoken
```

Out:

```
output/plans/ANTAR_0001_lane-b-pilot_picture.json   the whole plan, beat by beat
vault/clips/…mp4                                     the footage, hash-addressed
output/frames/…jpg                                   one poster frame a beat
```

Each beat's Hindi line names an object. The object table turns that into a
search in plain English, one clip is chosen for it, and the plan says exactly
when it is on screen — or, if nothing fits, a text card is drawn on the house
black instead.

---

# THE OBJECT TABLE

| | |
|---|---|
| Entries | **70** |
| How it matches | the whole line first, then the beat's own object hint, then nothing |
| Longest match wins | “वो फ़ोन” beats “फ़ोन” |
| A line naming nothing it knows | becomes a card, and the plan says why |

It holds nouns only — phones, mugs, walls, clocks, doors, windows, rooms. It
holds no feelings, no abstract words and no people, because a search for a
feeling returns a stranger's face.

---

# HOW A CLIP IS CHOSEN

| Rule | Setting |
|---|---|
| Shape | portrait only — anything wider than tall is refused |
| Height | at least **1280**, and **1080×1920 first** where the clip has it |
| Length | at least **3.0s**, aimed at 4.0s |
| Weight | 25MB a download, capped while streaming |
| Order | **deterministic** — same script, same seed, same clips, every time |
| Per video | a clip is never used twice in one video |
| Across videos | maximum **2** uses, then it is retired |
| Lookalikes | two clips within a Hamming distance of 4 count as the same clip |

The order is the point. Three clean runs an hour apart picked the **same seven
clips**, at the same sizes, in the same windows — because the choice is a hash
of the seed and the clip's address, not a dice roll.

---

# WHAT GOT REFUSED, LIVE

From the last clean run, straight out of the plan's own notes:

| Refused | Why | The library's own words |
|---|---|---|
| `pexels:7247828` | about a person | “a person touching a cellphone screen” |
| `pexels:19309492` | about a person | “christmas time tea and gingerbread man” |
| `pexels:8321912` | about a person | “an elderly man looking at a grandfather clock” |
| `pexels:8322013` | about a person | “a woman dancing with a wall clock” |
| `pexels:7646797` | about a person | “person opening the door” |
| `pexels:31702408` | about a person | “person approaching a blue door” |
| `pexels:7463920` | about a person | “man lifting the sofa” |
| `pexels:7318813` | **a face in the pixels**, at 0.88s, 4.39s, 6.15s | — |
| `pexels:6115073` | **a face in the pixels**, at 12.42s | — |
| `pexels:10524877` | **a face in the pixels**, at 0.54s, 1.61s, 2.69s, 4.84s | — |

**Ten refusals, and the video still has footage on all eight beats.**

The page address is read too. Pexels writes the description into the URL —
`elderly-man-using-a-stethoscope-8321896` — so a clip about a person is often
refused **before it is downloaded**, which costs nothing.

---

# NO FACES

The rule is absolute, so the check is not.

| What is checked | How |
|---|---|
| The search itself | the object table holds no person nouns, so the query cannot ask for one |
| The library's description | whole words only — “clock hands” is a clock, “chair” is not a “hair” |
| The page address | the slug is read as words before the download starts |
| **The pixels** | 8 frames sampled across the clip's real length, at half scale, frontal **and** profile cascades |

**Why two cascades.** The first version ran the frontal one only. A man sitting
side-on scored **0 faces out of 8** — and would have shipped. The profile
cascade scores that same clip **8 out of 8**. Across the eight clips first
chosen, the pair flagged exactly one. That is the proof, and it is also the
limit: this is a filter, not a promise.

---

# THE FRAME IS MEASURED, NOT ASSUMED

“No frame mostly black” is a blocking rule, and the cheap place to obey it is
before a grade would have to rescue a picture that was never in the file.

So every downloaded clip has one frame pulled, and the frame is measured:

| Shot | Light (0–255) | Black |
|---|---|---|
| 0 · फ़ोन | 176 | 1% |
| 1 · मग | 98 | 4% |
| 2 · दीवार | 131 | 0% |
| 3 · घड़ी | 139 | 0% |
| 4 · दरवाज़ा | 108 | 0% |
| **5 · खिड़की** | **20** | **36%** |
| 6 · कमरा | 127 | 0% |
| 7 · फ़ोन | 176 | 1% |

A clip over 55% black is refused outright. Beat 5 sits inside that limit but
nowhere near the 35–45 band — **that is the build stage's job, and it is written
down here rather than discovered later.**

---

# WHEN NOTHING FITS: THE CARD

A beat with no usable footage gets a text card on the house black, and the card
is measured too.

| | |
|---|---|
| Words on the card | the object's own Hindi word — never the whole line |
| Brightness | **solved, not chosen**: drawn once flat, drawn again 26 points up, the slope measured, the lift solved from it |
| Result | **39.8 / 39.9 / 39.9 / 40.0** across four test words, band is 35–45 |
| Pure black | never — the darkest pixel count on the card is 0 |
| Font | Khand Bold, sized to the card |

An early version used a fixed brightness lift. Three words came out at 44.4,
45.5 and 46.7 — outside the band, and it would have drifted further the moment
a longer word was drawn. A rule that only holds for the words you happened to
test is not a rule.

---

# THE PLAN IS A TIMELINE, NOT A LIST

The first plan gave each shot a length and no position. The lengths added up to
**29.48s against a 34.95s voice** — five and a half seconds of pauses belonged
to nobody, and any editor cutting to it would drift further out of sync with
every beat.

Now each shot carries an absolute **start** and **end**:

| Beat | On screen | Clip |
|---|---|---|
| 0 | 0.0 → 4.7s | 1080×1920 · 5.4MB |
| 1 | 4.7 → 9.5s | 1080×1920 · 13.5MB |
| 2 | 9.5 → 14.0s | 878×2048 · 2.7MB |
| 3 | 14.0 → 18.2s | 1080×2048 · 12.0MB |
| 4 | 18.2 → 22.8s | 1080×1920 · 8.8MB |
| 5 | 22.8 → 26.7s | 720×1280 · 5.1MB |
| 6 | 26.7 → 31.4s | 1080×2048 · 2.8MB |
| 7 | 31.4 → 35.0s | the same shot as beat 0, on purpose |

**The windows tile the whole track: 0.0 → 34.95s, no gap, no overlap.** The
0.85s before the payoff belongs to beat 6 — the room keeps sitting there while
the silence does its work — and the payoff cuts in on the frame the voice does.

Two things the plan says out loud rather than hiding:

- **“the same shot as beat 0, on purpose — the line comes back to it”** — a
  returning object is a rhyme, not a mistake, and a second clip would have
  broken it.
- **“the last word mark runs 0.13s past the sound — the shot ends with the
  sound, not the mark”** — the synthesiser overruns its own last word. The
  window still ends where the audio ends, and the column that does not add up
  is explained instead of being fudged to match.

---

# THE LIVE RUN

```
beats 8   clips 8   cards 0   downloads 7   refused 3   55.7MB
vault 7 clips, 0.05GB of 5.0GB
```

Seven downloads, eight shots: beat 7 is beat 0's clip, and it costs nothing to
show it again. Every clip is 1920-tall or better except beat 5, which is the
one clip in the batch that has no HD rendition on offer — so it took the
biggest file the clip has, rather than the smallest.

---

# NINE DEFECTS, FOUND AND FIXED HERE

| # | Defect | What it would have cost |
|---|---|---|
| 1 | The first live run **crashed**: opencv 5.0.0 removed `CascadeClassifier` | The stage did not run at all |
| 2 | A fixed brightness lift on the card | Cards outside the locked band |
| 3 | A frontal-only face cascade | A man sitting side-on shipped in the video |
| 4 | The repeat check ran on the listing | A lookalike cut is only visible in the pixels |
| 5 | A returning object got two different clips | The payoff line's rhyme, broken by accident |
| 6 | Clip uses counted per **run**, not per video | Re-rendering the same video retired its own footage |
| 7 | Shots had lengths but no positions | Every cut drifts, and drifts further each beat |
| 8 | The smallest usable file was downloaded | 720-wide footage stretched to a 1080 canvas — soft, and softness looks cheap |
| 9 | The frame was never measured | A black clip would have been found by the check suite instead of here |

**Defects 3, 5 and 7 were found by looking at the real output, not by a test.**
The contact sheet showed the man in the wall-clock clip and the phone appearing
twice with two different phones. The word timings showed the pause five and a
half seconds short. No test would have said a word.

---

# WHAT THIS PHASE PROVES

| Claim | How it is proved |
|---|---|
| Every beat has something on screen | Live run: **8 beats, 8 clips, 0 cards** |
| No people | 10 refusals recorded in the plan, 3 of them from the pixels, with the timestamps |
| The choice is deterministic | Three clean runs picked the same seven clips |
| The clip is no clip twice in one video | Enforced by key, tested |
| A clip is retired after two videos | Registry counts per video, tested |
| The card is in the band | Measured: 39.8–40.0, band 35–45 |
| The timeline matches the voice | Windows tile 0.0 → 34.95s of a 34.95s track |
| The stage survives no key at all | Offline test: 4 beats, 4 cards, nothing downloaded |
| It cannot silently ship a person | Face scan may be **absent**, and when it is, the plan says so in words |

---

# HONEST GAPS

| # | Gap | Impact |
|---|---|---|
| 1 | **Never executed on Windows** | Carried since Phase 1. Downloads use streaming, paths are UTF-8 — reasoning, not proof |
| 2 | **Pixabay has never been hit live** | It is the second library in the config and there is no key for it here. One library is one point of failure |
| 3 | **The face scan is a filter, not a promise** | Two cascades, 8 samples. A face at an odd angle, small, distant, or printed on a poster can still slip through |
| 4 | **No card has ever been needed live** | 8 of 8 beats found footage. The card path is proven by tests and measured brightness, not by a shipped frame |
| 5 | **Beat 5 is dark: 20/255** | Inside the black rule, outside the band. The build must lift it. If the build cannot, the answer is a different clip, not a brighter grade |
| 6 | **HD footage costs bandwidth** | 55.7MB for a 35s video. Fine at the 5GB vault cap — roughly 90 videos before pruning — but it is 55MB a video, not 29MB |
| 7 | **The vault has no learning yet** | The registry knows what was used; it does not yet know what worked |

**Gap 1 is still the one that matters.** It will stay until `START_ANTAR.bat`
runs on your machine.

---

# WHERE WE ARE

| Phase | State |
|---|---|
| 1 · Foundation | **Done, 93/100** |
| 2 · Words | **Done, 91/100** |
| 3 · Voice | **Done, 91/100** |
| **4 · Picture** | **Done, 92/100** |
| 5 · Build | Next — full-bleed vertical, Khand, grade, sound |
| 6 · Check | The check suite on a real MP4 |
| 7 · Details | Title score, description, tags |
| 8 · Panel | The 9 tabs |
| 9 · Proof | A test render scored, with numbers |
| 10 · Learn | The analytics loop |

**94 tests passing. Four phases above the bar.**

---

# THE ONE THING WORTH SAYING

**This phase's main job is refusing things.**

Ten clips were thrown away for this one video — most of them good footage, most
of them on the correct subject, several of them beautiful. They were refused
because a person was in them, or because the *library* said a person was in
them, or because the frame was black, or because the clip had been used twice
already.

The cost of a rule is one more search. The cost of letting a face through is a
promise broken in a published video, and a rule the rest of the studio can no
longer be trusted to keep.

**A studio that only obeys its rules when they are cheap does not have rules.**
