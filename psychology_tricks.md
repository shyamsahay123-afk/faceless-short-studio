# PSYCHOLOGY TRICKS SYSTEM — design spec (code lands with the text-layer step)

Goal (in the user's words): *indirectly signal to the brain that this channel
holds secrets and power, make viewers feel they are JOINING something elite —
plus comment-trigger mechanics (the planted-spelling-error principle).*

Two families. Every trick has: the brain mechanism, where it's implemented,
the frequency rule, and the overuse failure mode. Frequency rules matter more
than the tricks themselves — a trick used every video stops working by video 8.

=============================================================================
FAMILY A — COMMENT BAIT (algorithm fuel: comments = distribution)
=============================================================================

A1. THE PLANTED FLAW  (the user's spelling-error principle, systematized)
  brain : error-correction reflex + the status hit of being the one who noticed
  where : script_engine — 1 word in a BEAT line (never hook, never CTA) swapped
          to a near-miss ("discipline"→"discpline", "dopamine"→"dompamine") or
          one number nudged (99%→97%). Must be *almost* right so fixing is easy.
  rule  : once every ~10 videos (video_id % 10 == 7), tracked in db so it never
          repeats on back-to-back videos
  fail  : more frequent = channel reads as incompetent, not "caught in the act"

A2. THE OPEN QUESTION  (answer lives only in comments)
  brain : Zeigarnik open loop + "I have an opinion" reflex
  where : script_engine CTA pool — one CTA variant ends on a fork the video
          never answers: "Which one were you — day one, or year one?"
  rule  : 1 in 3 videos
  fail  : every-video = starts feeling like a survey, not a secret

A3. THE HIDDEN DETAIL  (rewatch trap)
  brain : discovery + bragging rights; a second view to "prove" they saw it
          = loop rate boost
  where : style_engine — 1-frame flash (1/24s) of a small symbol at ~70% of
          the video, position seeded from video id. Never announced in-video.
  rule  : every video carries one; the channel's OWN account hints at it in
          comments on ~1 in 5 videos ("some of you spotted it.")
  fail  : announcing it in the video = the hunt dies

A4. THE DEBATE SPLIT
  brain : social identity — people defend their camp
  where : script_engine — one value beat phrased as a camp divider on
          HABITS/PREFERENCES only (never identity groups — safety line):
          "Early risers are just anxious with a routine."
  rule  : 1 in 4 videos
  fail  : offensive splits = hostile comments = the algorithm reads it as negativity

A5. THE PLANTED WRONG ANSWER  (higher-stakes version of A1)
  brain : expert-correction reflex — the comment section becomes a mini
          lecture, which makes the video look authoritative by association
  where : script_engine — one fact line with a subtly wrong technical claim
          (nuance zone only: "the prefrontal cortex makes all decisions" when
          it's the basal ganglia that run habit loops)
  rule  : 1 in ~15 videos; NEVER something that actually misleads harmfully
  fail  : a wrong claim that's actually true damage = trust collapse

=============================================================================
FAMILY B — SECRET / POWER SIGNALING (the "inner circle" feeling)
=============================================================================

B1. THE GATEKEEPER LINE  (identity elevation)
  brain : self-selection — "if I'm still here, I'm the kind who gets it"
  where : script_engine hook/mid pools:
          "99% will close this in the next ten seconds. That's fine."
          "If this found you, you've been feeling this for months."
  rule  : 1 in 3 videos (hook or mid)
  fail  : every video = arrogance

B2. THE NAMED SECRET  (tribal vocabulary) — THE CORE TRICK
  brain : naming = ownership; once a concept has a name, viewers USE the name
          in comments → the comment section becomes the channel's own language
  where : script_engine — every video introduces exactly ONE named concept
          ("the dopamine tax", "micro-friction", "the 20-minute loop"); the
          name is rendered as a BEAT card by the elite text layer
  rule  : EVERY video (this is the GOONINGGNG model — "scientists call it…")
  fail  : two names per video = neither sticks

B3. BORROWED AUTHORITY  ("scientists call it X")
  brain : authority transfer + the leaked-knowledge feeling
  where : script_engine hook/value pool: "Neuroscientists have a name for this."
          (genre convention, not fake citations — no invented study numbers)
  rule  : 1 in 3
  fail  : overuse = every sentence sounds like a press release

B4. THE DAILY CODE  (the power ritual — strongest item on this list)
  brain : ritual + shared secret; a code that changes daily turns the comment
          section into a daily event and the channel into "the place that
          hands you codes" = power signaling at its purest
  where : style_engine outro card — "CODE 4-2-1" bottom-left, 3 digits,
          deterministic from the render date (logged in db). User optionally
          pins it or leaves it undiscovered
  rule  : every video, small, never explained
  fail  : explaining it = the ritual dies

B5. THE SIGIL FRAME  (insider mark)
  brain : pattern recognition + "only the real ones notice"
  where : style_engine — one small channel glyph (initial or a 12-point star)
          appears once per video for 2s, position seeded per video id
  rule  : every video, one appearance, never announced; pairs with A3
  fail  : too often = watermark, not secret

B6. THE EXCLUSIVE CLOSE  (reverse flattery)
  brain : exiting with "I discovered this" instead of "I was sold this"
  where : script_engine CTA pool: "You didn't find this video by accident."
  rule  : 1 in 4
  fail  : every video = cult tone, which the YouTube audience punishes

=============================================================================
THE TRICK DIRECTOR (the "AI chooses" logic — same pattern as the SFX director)
=============================================================================
Every video gets, automatically:
  ALWAYS : B2 (one named secret) + B4 (the code) + B5 (the sigil)
  ROTATE : one bait from A (A2 → A3-tease → A4 → A2 …, no repeat within 3 videos)
  SCHEDULE: A1 planted flaw when video_id % 10 == 7 · A5 when % 15 == 11
  STATE  : last-used tricks stored in the db settings table (rotation memory)
  LOG    : studio.log gets one line per video:
           TRICKS #12: secret='the dopamine tax' bait=A2 code=7-3-1 flaw=none
Why log it: the Performance Log gains a COMMENTS column, and after ~20 videos
you can see which bait actually moved comments-per-1000-views. Keep the best
2, drop the rest. The system tunes itself on your own data.

CONFIG (daily_settings.json, extend later):
  "tricks": {"enabled": true, "always": ["named_secret","code","sigil"],
             "baits": ["open_question","hidden_detail","debate_split"],
             "flaw_every": 10, "wrong_answer_every": 15}
