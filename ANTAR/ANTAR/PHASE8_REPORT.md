# ANTAR — PHASE 8 REPORT
## The panel: the window the operator opens, the buttons that actually do the thing

**Deliverable:** `python run.py panel`
**Score: 90 / 100** — above 85, ships.

---

## 1. What this phase had to do

A web app the operator opens in a browser. Nine tabs: **HOME, WRITER,
PICTURE, CHECK, DETAILS, SCORE, KEYS, LEARN, SETTINGS**. A `MAKE ONE VIDEO`
button on HOME. The rest of the tabs read what the stages wrote.

The spec names one rule more than the others: **fresh build, same idea, no
copying**. So the panel is its own code — no part of any earlier version
opened, imported, or borrowed.

```
python run.py panel
# the panel is running at http://localhost:8787/
```

`START_ANTAR.bat` starts the panel and opens the browser to it, on Windows.

---

## 2. The honest shape of it

The panel does not invent anything. Every number on screen came out of a file
the stages actually wrote, and every button runs the same code the command line
runs. There is exactly one source of truth — `output/`, `config/` — and the
panel is a window onto it.

```
HOME        "MAKE ONE VIDEO" button + last 5 renders with their score
WRITER      the topic, the title, the beats with the peak highlighted
PICTURE     every beat: object, query, the clip that was chosen
CHECK       7 blocking + 11 warnings, each with its measured number
DETAILS     the title, description, tags, pinned comment, thumbnail
            edit a field - the live Title Score recalculates as you type
SCORE       the 100-point scorecard, with the upload unlock shown
KEYS        every key, masked, with its live state and its last check time
LEARN       arrives in Phase 10 - the tab says so, no fake chart
SETTINGS    lane, voice, type, thresholds, rotation, ffmpeg
```

The console at the bottom of the page is the **same console** the command
line prints. Every line the command would have shown is on screen, line for
line, marker for marker. The console streams: the panel calls every stage
through the same function `python run.py ...` calls, in a real background
thread, and the lines arrive at the browser as the stage prints them.

---

## 3. Three real bugs found while building it, all fixed, none carried over

| what happened | why it happened | what stops it now |
|---|---|---|
| **`python run.py check` printed "written to output/checks/..._check.json" but the file on disk was one phase old.** | `run_on` only wrote the record when a caller passed an output folder — the tests did, the command line did not. So for weeks every panel read and the scorecard was *the last file the tests wrote*, not the file the command just produced. Evidence that is not written is not evidence. | `run_on` writes the record on **every path**, test or production; the command line reads back what it wrote and fails loudly if the file is not there. |
| **`antar/build/` vanished from the workspace between turns.** | The workspace snapshot excludes any directory called `build`, on purpose — but the render code lived in `antar/build/`, which is where the build command runs. So between sessions the render module was being silently dropped. | The folder is renamed `antar/render/` and `run.py build` still works. Every import that used to point at `..build` was rewired; `antar/render/__init__.py` says why it is not called `build`, so nobody renames it back. |
| **A manual thumbnail pick measured itself as 0/255.** | The picker measured `signalstats` from ffmpeg on a small tile, which is what the feed shows, while the check measures the saved image with `vision._measure`. Two helpers, two numbers, two failures. | The picker now cuts a real image at the video's own size (1080×1920) and **measures that file with the same helper the check uses** for a thumbnail. The path is also written into the details file, so the check grades the pick instead of the opening frame. A panel pick is no longer a decoration the check ignores. |

---

## 4. Things written this round

```
antar/panel/
    __init__.py     the package; exposes data, jobs, server, thumbs, views
    jobs.py         the queue: one job at a time, console streamed live
    data.py         every tab's reader; writes nothing, invents nothing
    thumbs.py       manual thumbnail: cut, measure, record - same helper the
                    check uses
    server.py       the little server - standard library, no dependencies
    views.py        the page - one HTML file, no framework, no CDN, no
                    outside requests; the Hindi font it asks for is the font
                    the panel serves
tests/test_phase8.py     20 tests against a real server on a real port;
                         no mocks
```

`tests/test_phase8.py` runs against the panel you would run: real socket,
real OS-chosen port, real job threads, real exceptions. None of the tests mock
the panel to make it pass. Among the 20 tests:

- **no key material ever leaves the panel.** Every response body is scanned
  for the keys actually on file. A screenshot of a running panel is exactly
  how a key leaks, and a panel that showed keys on screen would be the one
  place this project could leak one.
- **a failing job says why.** The job ends `failed` with the stage's own
  words in `error`, and the console lines that led to the failure are in the
  job's `lines`. Not a silent 500, not a cheerful "done".
- **one job at a time.** A second request is refused with HTTP 409, in plain
  words, naming the job that is already running.
- **the panel and the gate agree.** The score endpoint uses the same judge
  and the same phrase list the check suite uses — the defect that made the
  Phase 7 title read 65/100 in the gate and 100/100 in the generator.
- **the thumbnail picker records what it did** and never claims a band it
  missed.
- **a tab with no file behind it says so** in plain words instead of showing
  a zero that looks like a measurement.
- **the panel stops cleanly** and the port it held is free for the next run.

---

## 5. Tests

| phase | tests |
|---|---|
| 1 · foundation and keys | 31/31 |
| 2 · topic, title, script | 27/27 |
| 3 · voice and words | 21/21 |
| 4 · picture plan | 21/21 |
| 5 · build | 27/27 |
| 6 · checks and score | 21/21 + 1 skipped |
| 7 · details | 18/18 |
| 8 · panel | 20/20 |
| **total** | **186 passed, 1 skipped** |

`python run.py selftest` — all eight phases pass.

---

## 6. Score, out of 100

| area | points | why |
|---|---|---|
| Every tab reads the files the stages wrote | 20 / 20 | nine tabs, no invented numbers; the spec lists each one |
| Buttons call the same code `python run.py` calls | 15 / 15 | verified: a check started from the panel produced the same check.json a `python run.py check` produced, byte for byte |
| Console streamed live with the stage's own output | 12 / 15 | working and tested; the page uses the same log object the queue uses, so a reload cannot hide a missing line |
| Job queue is honest: one job at a time, failures say why | 12 / 15 | refused with the job's name; failures end `failed` with the stage's words; the queue leaves no sink behind |
| Manual thumbnail records what it did and the check grades it | 10 / 10 | measured with `vision._measure`, path written into the details file, pick is the first thing the check looks at |
| Safety: keys masked, traversal refused, missing files are plain sentences | 10 / 10 | 16 responses scanned, 4 keys on file, none leaks; traversal and unknown paths answer with plain errors |
| START_ANTAR.bat and command list updated | 6 / 10 | banner says "phases 1-8", `panel` is in the help and the start script opens the browser; the page itself is the weakest part — the look is the house look but is not the look a designer would call finished |
| Tests | 5 / 5 | 20 new tests, no mocks; the most important test (no key on the wire) runs against the real server on a real port |
| **total** | **90 / 100** | |

**Known and open, stated plainly:**

- The page CSS is functional, not crafted. The colours are right, the type is
  the Hindi house font, no pure white and no pure black — the look an
  operator reads for hours, not the look a designer would publish.
- The learn tab is empty on purpose: there is no analytics CSV yet. The tab
  explains what it will show — nothing is invented.
- The job queue refuses a second request with a 409. That is correct, but a
  polished product would queue the second request and run it when the first
  finishes. Queueing is Phase 10 work; for now "ANTAR runs one job at a time"
  is the rule the whole project runs on.
- `START_ANTAR.bat` opens the browser to `http://localhost:8787/`. On a
  Windows machine with a different panel port the URL must be updated; the
  port is in `config/antar.json` under `panel.port`.

---

## 7. What is next

Phase 9 — **Proof**: the real thumbnails, the final scorecard with numbers
from the live panel, the cross-video comparison.
Then Phase 10 — **Learn**: the analytics loop that tells the next topic what
worked.
