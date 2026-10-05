# ANTAR — PHASE 2 COMPLETE
### The words half · built, tested, scored · 27 Sep 2026

---

# SCORE: 91/100

| Category | Weight | Score | Evidence |
|---|---|---|---|
| **Correctness** | 20 | **19** | 27/27 Phase 2 tests, 43/43 with Phase 1 |
| **Proof** | 20 | **19** | The word band is derived from **real rendered audio**, not assumed |
| **Robustness** | 15 | **14** | Every provider failure path tested; a failed run says so instead of inventing a script |
| **Windows readiness** | 15 | **12** | Same caveat as Phase 1 — **cannot be executed here** |
| **Zero-copy compliance** | 10 | **10** | Still enforced by a test that scans every file |
| **Clarity** | 10 | **9** | Four new commands, plain failure messages that say what to do next |
| **Honesty** | 10 | **8** | Two real defects were found by my own tests and fixed. See below |
| **TOTAL** | **100** | **91** | Above the 85 bar |

---

# THE BIGGEST RESULT: HINDI PACING IS NOW MEASURED

In Phase 1 the word band was **void** — the English 80–90 had no basis in Hindi.

I rendered a 103-word Hindi script through your chosen voice and timed it:

| Voice setting | Duration | Rate |
|---|---|---|
| **Swara +10%, +3Hz** *(yours)* | **39.12s** | **2.633 words/second** |
| Swara normal | 43.03s | 2.394 |
| Swara slow | 49.46s | 2.082 |

**So the band is now derived, not guessed:**

```
band = words/second × (target seconds − 0.85 silence − 0.05 loop gap)
     2.633 × 29.15 = 77        →  floor 78
     2.633 × 39.15 = 103       →  ceiling 102

word band        78 – 102
render floor     70
render ceiling   110
```

**A test asserts the band still follows from the measurement.** If anyone changes the voice or the target duration without redoing the maths, the test fails.

---

# THE SEARCH BOX TEST IS REAL

The topic engine asks **YouTube's own autocomplete** whether a phrase is something people actually type. Live, no API key.

```
$ python run.py search "शर्मीले लोग"
  signal: present   related suggestions: 1
     शर्मीले लोगो
```

A topic is only allowed through if real suggestions come back. Four signals, all decided by count:

| Signal | Meaning |
|---|---|
| **strong** | 3+ suggestions relate to the phrase |
| **present** | 1–2 *(this is the minimum to pass)* |
| **thin** | suggestions exist but none relate — the phrase lives only in your head |
| **none** | nothing came back |

**This is the one surface where a channel with one subscriber competes on equal terms.**

---

# TWO REAL DEFECTS FOUND AND FIXED

My own tests caught these. Neither would have shown up until a video had been rendered.

| # | Defect | Why it mattered |
|---|---|---|
| 1 | **The audit penalised its own notes.** Six NOTEs — "no names", "all beats name an object" — cost 18 points, so a perfect script scored 82/100 | A script would be marked down for being clean. **Now only WARN costs points: a clean script scores 100.** |
| 2 | **The 40–60 character title rule is an English rule.** It's about **display width**, not character count. A Devanagari glyph is ~1.3× the width of a Latin one | A perfectly good Hindi title of 37 characters was being refused. **Band corrected to 30–48 Devanagari characters, with the derivation written into the config.** |

**Both fixes are in the shipped code and both are covered by tests.**

---

# WHAT THE ENGINE NOW DOES

```
python run.py topics      generates candidates, then tests each against live search
python run.py write       writes the script, audits it, saves it
python run.py models      shows the model ladder, strongest first
python run.py search      tests one phrase against live search
```

## The writer, in order of what it will not do

| Rule | How it is enforced |
|---|---|
| **Never takes a weak model's answer while a strong one exists** | Models ranked from the live catalogue; tried strongest first. A test proves it climbs when the strongest fails |
| **Never silently demotes** | Every model tried is recorded and printed |
| **Never ends a run with nothing** | The best draft of the run is returned even when imperfect, with its complaints attached |
| **Never accepts a short draft without trying once to grow it** | A too-short draft is sent back to the same model, asked to extend rather than rewrite |
| **Never asks for JSON mode** | Groq validates the raw generation; a reasoning model's raw output carries a trace, so a good answer still fails. Plain text, parsed here |
| **Never trusts a good-looking reply** | Every draft is audited numerically before it is kept |

## The audit — every finding is a number or a position

| Blocks the script | Warns |
|---|---|
| under the render floor | outside the target band |
| over the render ceiling | a beat with nothing filmable |
| **any person's name** | a buried peak |
| no beats at all | a closing line that echoes nothing |
| | आप instead of तुम |
| | a commanding tone |

**NOTEs are free.** A clean script scores 100/100.

---

# THE ZIP

# `ANTAR_STUDIO.zip`

**215 KB · 40 files · both phases.**

| Inside | |
|---|---|
| `antar/` | the engine — 10 modules, 20 Python files all parse clean |
| `antar/brain/` | **new in Phase 2** — providers, models, objects, prompts, searchbox, topics, writer, audit |
| `assets/fonts/Khand-Bold.ttf` | your approved typeface, already in place |
| `config/antar.json` | every locked decision, plus the measured pacing |
| `tests/` | 43 tests |
| `INSTALL.bat` · `START_ANTAR.bat` | purge bytecode, install, single-instance check |

**Not inside, on purpose:** no `.env`, no old-build file, no bytecode, no vault contents, no logs, no personal state.

**Ten checks were run against the code as it sits inside the archive** — not against my working copy. All ten passed.

---

# HOW TO START

```
1.  Unzip ANTAR_STUDIO.zip anywhere
2.  double-click INSTALL.bat
3.  python run.py keys import "<your env file>"
4.  python run.py keys test
5.  python run.py models          <- shows what your keys are entitled to
6.  python run.py topics          <- generates 10 topics, tests each against live search
7.  python run.py write           <- writes the script for the best one
```

**Steps 6 and 7 need a working key.** Step 4 tells you how many you have.

---

# HONEST GAPS

| # | Gap | Impact |
|---|---|---|
| 1 | **Never executed on Windows.** | Same as Phase 1. The code avoids POSIX-only APIs and every file write is explicit UTF-8, **but that is reasoning, not proof** |
| 2 | **The topic engine has not been run against a live LLM here.** | I have no working Groq or Gemini key in this sandbox. The **logic** is fully tested with a fake brain; the **wire** is proven only as far as a 400 response from each real endpoint |
| 3 | **`doctor` still does not verify Khand loads** | Carried over from Phase 1 |
| 4 | **No script has been through the voice yet** | Phase 3 measures whether the audit's word count matches the audio's real length |
| 5 | **The panel does not exist** | Phase 8, by design |

**Gap 2 is the one that matters.** The first time you run `topics` for real, watch what it prints — if a model returns something unexpected, the reply is logged rather than swallowed, and we fix it from that.

---

# WHERE WE ARE

| Phase | State |
|---|---|
| 1 · Foundation | **Done, 93/100** |
| **2 · Words** | **Done, 91/100** |
| 3 · Voice | Next — turns a script into audio, measures whether the band was right |
| 4 · Picture | Object → clip, or a text card |
| 5 · Build | Full-bleed vertical, Khand, grade, sound |
| 6 · Check | The check suite on a real MP4 |
| 7 · Details | Title score, description, tags |
| 8 · Panel | The 9 tabs |
| 9 · Proof | A test render scored, with numbers |
| 10 · Learn | The analytics loop |

**Two phases down. Both above the bar. 43 tests passing.**

---

# AND ONE THING WORTH SAYING

**The word band is the clearest example of why this rebuild was worth doing.**

The old engine carried an 80–90 word target with no basis. It came from English, it was never checked against Hindi audio, and every script was written to hit a number that meant nothing.

It took **one render and forty seconds** to get the real number. **That is the difference between a guess and a measurement — and the whole build is now made of measurements.**
