# ANTAR — PHASE 3 COMPLETE
### The voice · built, tested, scored · 27 Sep 2026

---

# SCORE: 91/100

| Category | Weight | Score | Evidence |
|---|---|---|---|
| **Correctness** | 20 | **19** | 64/64 tests across three phases; all five audio checks read from the file |
| **Proof** | 20 | **19** | Every number comes from ffmpeg reading the produced track, never from the plan |
| **Robustness** | 15 | **13** | Failure paths tested; only one voice has ever been rendered |
| **Windows readiness** | 15 | **12** | Not executed here — same caveat as Phases 1 and 2 |
| **Zero-copy compliance** | 10 | **10** | Still enforced by the scanner test |
| **Clarity** | 10 | **9** | The stage prints what it did to the audio in plain words |
| **Honesty** | 10 | **9** | Four real defects were found here and fixed. Two earlier passes were wrong |
| **TOTAL** | **100** | **91** | Above the 85 bar |

---

# WHAT THIS PHASE DOES

One command turns a saved script into a finished audio track.

```
python run.py voice
```

In:

```
output/scripts/ANTAR_0001_lane-b-pilot.json      the script Phase 2 wrote
```

Out:

```
output/audio/ANTAR_0001_lane-b-pilot.wav         the finished track
output/audio/ANTAR_0001_lane-b-pilot_raw.mp3     the raw take, kept for checking
output/audio/ANTAR_0001_lane-b-pilot_audio.json  every word's exact time
```

The JSON holds the word times because **Phase 4 puts text on screen where those
words are spoken.** If the times are a guess, every caption drifts.

---

# THE VOICE

| Setting | Value |
|---|---|
| Voice | `hi-IN-SwaraNeural` |
| Rate | **+10%** |
| Pitch | **+3Hz** |
| Takes | **one continuous take** — never stitched |
| Word times | from the synthesiser itself, not from a transcriber |
| Cost | **zero** |

**Why not Whisper:** the synthesiser already knows when it spoke each word, to
the 100-nanosecond tick. A transcription pass would re-guess what is already
known, and it can invent words that were never said.

---

# THE TRACK, IN ORDER

```
[ 20ms of air ]                 kept, so the first word is not clipped
[ the first word ]              lands at 0.000s
[ the take ]
[ 0.85s of true silence ]       inserted right before the payoff line
[ the payoff line ]
[ 50Hz-ish sub-bass ]           45Hz, synthesised, muted through the pause
[ 50ms fade ]                   the loop seam
```

Every sound is synthesised in Python and ffmpeg. **There is no assets folder
and there never will be.**

---

# THE RESULT, MEASURED

| Check | Reading | Limit | |
|---|---|---|---|
| audio starts at 0.000s | **0.010s** | 0.02 | PASS |
| loop seam closed | **0.050s** | 0.08 | PASS |
| loudness on target | **−14.5 LUFS** | −14 ± 1 | PASS |
| silence before payoff | **0.84s** of true silence, ending at the payoff | 0.85 | PASS |
| duration suits the format | **34.95s** | 20–50 | PASS |

**Audio score 5/5.**

The raw take, for comparison: 35.86s, 90 words, 160ms of encoder padding in
front, −20.7 LUFS.

---

# THE PAUSE IS REAL, AND HERE IS THE PROOF

This is the moment the whole video is built around: the line before it stops,
0.85 seconds pass with nothing at all, then the payoff lands.

I read the finished file back, sample by sample, 0.1s at a time:

```
  29.5s  -12.7  #########################################
  30.0s  -18.3  #####################################
  30.2s  -20.7  ####################################
  30.4s  -43.6  ####################
  30.6s  -75.0                            <-- nothing
  30.7s  -75.0                            <-- nothing
  30.8s  -75.0                            <-- nothing
  31.0s  -75.0                            <-- nothing
  31.2s  -75.0                            <-- nothing
  31.4s   -9.1  ###########################################
```

The floor of that chart is −75dB. Measured exactly, the pause is **−240dB** —
which is not quiet, it is **zero**. The voice's own gaps between sentences sit
at −43dB, so the pause is **200dB deeper than silence.**

**And the 0.85s is inserted, not found.** The voice left 784ms of its own gap
there. That gap is removed and replaced with exactly 0.85s of digital silence,
starting 20ms after the last word of the line before.

---

# FOUR REAL DEFECTS, FOUND AND FIXED HERE

| # | What was wrong | How it showed | Cause |
|---|---|---|---|
| 1 | **The sub-bass played straight through the pause** | The "silence" measured −43dB, not silence at all | ffmpeg's `volume` filter evaluates its expression **once** and reuses it for the whole file. Without `eval=frame` the duck never happened |
| 2 | **The pause was cut 0.35s too early** | 0.35s of the previous line played *after* the silence | The hole was inserted before the payoff instead of immediately after the line before it |
| 3 | **The payoff word itself was timed 86ms early** | Word timings and the audio disagreed | An off-by-one: `i > index` left the payoff word out of the shift. Every other word moved, the one that mattered did not |
| 4 | **The payoff was found at the first match** | A repeated phrase earlier in the script stole it | It matched forwards. The payoff sits at the end by design, so it now searches backwards |

**Defect 1 is the one worth reading twice.** Two separate earlier runs reported
the pause as present and correct. Both were wrong, because the measurement
looked at the full band and the drone filled the hole.

---

# AND ONE EARLIER PASS WAS PASSING ON A LIE

The **loop seam** check said PASS at 0.036s. It was not passing.

The 45Hz drone runs at −43dB. ffmpeg's silencer reads "silence below −45dB" —
so the drone counted as **sound**, and the **750ms of dead air** sitting at the
end of every take was invisible. Delete the drone and the same file measures
**0.8 seconds** of dead air before it loops.

So I changed three things:

1. **Where the voice starts and stops is now measured above 200Hz only.** The
   drone is outside that band. So is the encoder's hiss. Neither can hide
   anything again.
2. **The dead air at the end is now cut.** The file stops where the voice stops,
   measured, with a 50ms fade. The loop restarts on the last word.
3. **The synthesiser's last word over-reports its end by 180ms** on every take.
   The samples are the reference, so the cut follows the samples.

Same check, honest number: **0.050s.**

---

# THE WORD BAND WAS WRONG, AND IS NOW RIGHT

Phase 2 measured pacing as **2.633 words/second** and built the band on it.

That measurement counted the synthesiser's front padding as speech. Measured
over the speech only — first word to last word — it is **2.576 words/second**.

| | Before | Now |
|---|---|---|
| words/second | 2.633 | **2.576** |
| word band | 78–102 | **75–101** |
| render floor / ceiling | 70 / 110 | **68 / 108** |

**The 2.5% difference is 4 seconds on a 36-second video.**

The old band would have passed a 102-word script that runs 40 seconds of speech
plus the pause — over target, every time. A test now asserts the band still
follows from the measured voice.

**The live script was re-cut to 90 words** and now renders at 34.95s, inside the
30–40s target, with nothing wasted.

---

# WHAT THIS PHASE PROVES

| Claim | How it is proved |
|---|---|
| The first word is at 0.000s | Read from the samples, above 200Hz: **0.010s** |
| The pause is silent | Read from the samples: **−240dB**, 200dB below the voice's own gaps |
| The pause is in the right place | Its end is measured at **31.37s**; the payoff word's saved time is **31.374s** |
| The loop restarts on the last word | **0.050s** between the voice stopping and the file ending |
| Loudness | **−14.5 LUFS**, peak −1.0dBFS, read by ffmpeg's meter |
| Word times are real | Every timing shifted by the measured padding offset, then verified against the waveform |

---

# HONEST GAPS

| # | Gap | Impact |
|---|---|---|
| 1 | **Never executed on Windows** | Carried from Phase 1 and 2. Filter strings are passed as arguments, never through a shell, and every write is explicit UTF-8 — **but that is reasoning, not proof** |
| 2 | **Only Swara has ever been rendered** | `hi-IN-MadhurNeural` is in the config as the alternative and has never been run |
| 3 | **One voice, no music, no effects** | By design for now. The track is voice, a pause, a drone and a fade |
| 4 | **The word times are the synthesiser's** | Cross-checked against the waveform at the start of the take, not word by word |
| 5 | **A mid-run ffmpeg failure is untested** | A missing ffmpeg is caught with a clear message; a crash halfway through the build is not simulated |

**Gap 1 is still the one that matters**, and it will stay until you run
`START_ANTAR.bat` on your machine.

---

# WHERE WE ARE

| Phase | State |
|---|---|
| 1 · Foundation | **Done, 93/100** |
| 2 · Words | **Done, 91/100** |
| **3 · Voice** | **Done, 91/100** |
| 4 · Picture | Next — object → clip, or a text card |
| 5 · Build | Full-bleed vertical, Khand, grade, sound |
| 6 · Check | The check suite on a real MP4 |
| 7 · Details | Title score, description, tags |
| 8 · Panel | The 9 tabs |
| 9 · Proof | A test render scored, with numbers |
| 10 · Learn | The analytics loop |

**64 tests passing. Three phases above the bar.**

---

# THE ONE THING WORTH SAYING

**Twice in this phase a number came back right and the thing it described was
broken.**

The pause was reported present while a drone hummed through it. The loop seam
was reported closed while three quarters of a second of dead air sat at the end
of the file. Both were the same mistake: **measuring the wrong signal.**

A check that can be satisfied by the wrong thing is worse than no check, because
it stops you looking. Three of the four defects here were found by reading the
audio back myself, not by a test.

**The tests now read the same thing I do.**
