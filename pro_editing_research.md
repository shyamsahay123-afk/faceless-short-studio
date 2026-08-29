# PRO EDITING RESEARCH — THE COMPLETE "WHEN TO DO WHAT" MANUAL
Date: 2026-08-27 | Research only (no code yet)
Sources: measured user render (39.9s, ref4) + vocal chain guides 2026 (mixinggpt, rypsup, r/audioengineering) + ducking/mixing standards (zella, instademo, sonilo, r/VideoEditing) + cut/transition studies (cutfast, capcut, insideeditors, adobe, quora)

## 0. WHAT I MEASURED IN YOUR VIDEO (baseline)
- Cuts: 0.8/1.8/2.8 (1s hook) → gap 1.9s → **gap 5.5s (4.7→10.2)** → burst 11.6-13.1 (card) → steady 1.1-1.7s
- Luminance: bright flash ~1s + ~3s; bright end 37-38s; dark 38.5-39.2; mid 39.5+
- Audio: fade-in 0.2-0.4s; breathing dips at 16s/26s (0.032); fade-out last ~1s
- Music: continuous bed 0-39s, swell 12-14s (card burst ✓), micro-dips 16/28/36s
- Verdict: your video is ALREADY 70% pro-shaped. The gaps below are the remaining 30%.

## 1. VOICE (tone + processing)
PRO CHAIN (order matters):
1. HPF 80-100Hz (remove rumble)
2. Subtractive EQ: -3dB @ 300Hz (murmur), -2dB @ 5kHz (harshness)
3. Compression: 2-3dB gain reduction, medium attack — MULTI-STAGE (tone comp + final glue ≤2dB), never one crusher
4. De-esser: 2.5-4.5kHz, ~3dB reduction (AFTER compression — comp amplifies sibilance)
5. Additive EQ: +1-2dB @ 3-5kHz (presence), air shelf +1-2dB @ 10-16kHz (the "expensive" air)
6. Light saturation (warmth/harmonics — the "warm" tone faceless channels have)
7. Final LA-2A-style comp 1-2dB (glue)
LEVELS: voice = loudest element, -6 to -12dB peak, normalize mix to -14 LUFS
YOUR GAP: raw edge-tts voice — no compression/air/de-ess/warmth. Reference #3's voice sits ON TOP of everything; yours floats.

## 2. MUSIC (level + ducking + structure)
- Level: 12-18dB BELOW voice during speech (shorts feel right ~12-15dB; music-forward montage -3 to -6)
- Ducking: attack <300ms (fast), release slow (asymmetric = "breathing, not pumping"); 70-85% reduction, NEVER mute
- THE ARC (this is the pro secret):
  1. STRONGER INTRO — bed enters confident ON a beat BEFORE first words, then ducks as speech starts (the intro swell is part of the hook)
  2. SWELLS in gaps ≥2s (music "earns its place" in the silence)
  3. OUTRO FADE — last 1-2s fade, never dead stop
- Snap bed entrance to the first energy onset of the take
YOUR VIDEO: bed continuous ✓, swell at card ✓, dips ✓, fade-out ~1s ✓ — but intro enters FLAT (no beat-locked swell). Good bones.

## 3. SFX
- Level: -15 to -18dB (louder than music, quieter than voice)
- Your 5-SFX budget ✓ (hit/whoosh/ding+impact/loop)
- Pro nuance: SFX should hit ON the spoken power word (sample-accurate), not on the cut

## 4. CUTS (when + rhythm)
- Shorts: HARD CUTS are the default (momentum, zero delay)
- Shot length: 1-2s fast content; **NEVER let a cut stall >2.5s** (your 5.5s gap = #1 risk)
- Cut ON motion/action (disguises the cut); cut on the word, not after it
- J/L CUTS: use 1-2 per 30-60s short, MID-VIDEO ONLY (never first 3s)
  - J-cut: next shot's audio arrives 0.5-1s BEFORE picture (attention lead)
  - L-cut: voice continues while picture changes (THE explainer standard: narration unbroken, B-roll cuts freely)
- "Hard-soft cut" = 3-4 frame dissolve (invisible polish on awkward cut points)
- Priority order: content > rhythm > polish (never fancy transitions over bad rhythm)

## 5. TRANSITIONS (when each)
| Transition | Use when | In your video |
|---|---|---|
| Hard cut | Default, every beat | ✓ default |
| 3-4 frame dissolve | Awkward cut point polish | not used |
| Light flash (yours) | Reserve for 3 moments ONLY: hook→content, reveal, ending | currently on EVERY cut = dilutes |
| Speed ramp/whip | Energy spikes (mid-video burst) | not used |
| Dip-to-dark | Final beat / theme break | not used |
| Slow crossfade | NEVER in shorts (kills momentum) | — |

## 6. FADES (video + audio timing)
- VIDEO fade-in: SHORTS SKIP IT — hard cut into the hook at 0.0s (you do this ✓). Slow fade-in = lost hook
- VIDEO fade-out: clean dip-to-dark 0.5s on the final frame (optional; or freeze final beat 0.5s)
- AUDIO fade-in: 0.5s (yours 0.2-0.4s = fine, punchy)
- AUDIO fade-out: last 1-2s (yours ~1s ✓)
- Your ending: bright 37-38 → dark 38.5-39.2 → mid 39.5 = muddy. Pro: final beat on a clean frame → 0.5s dip-to-dark → audio fade finishes inside it

## 7. FILTERS / GRADE
- Your current grade (mid-gray darkening + contrast + saturation comp) = matches "dark premium" standard ✓
- Pro extras: +15-20% contrast/sat for Shorts compression crush (you have it ✓); grain 2-4% (you have it ✓); skin-tone protect (HSL) for any face clips
- ONE consistent LUT across the whole channel = identity (like the channel system)

## 8. WHEN TO SHOW THE LIST (card timing — your question)
PRO RULE: the card is a CLIMAX DEVICE, not a prop:
- First 30% of the video = hook + first value (NO card — it kills the hook's momentum)
- Card appears (redacted) at **30-45%** mark
- REVEAL at **60-70%** mark (the loudest moment of the video)
- Before/After at **75-85%**
- Final 15% = payoff + loop line
YOUR VIDEO: card at ~12% (5s of 40s) = TOO EARLY. It front-loads the climax, so the back half has no peak.

## 9. THE 40-SECOND TIMING SHEET (when to do what — the whole manual in one table)
| Time | Action |
|---|---|
| 0.0-0.3 | Hard cut into content (NO video fade-in). Music intro swell ON beat. Audio 0.2s ramp. Hit SFX 0.4 |
| 0.3-3.0 | HOOK: 3 cuts @ ~1s each. Hook text staggered. Fastest zone of the video |
| 3.0-8.0 | Value beat 1: cuts 1.5-2s. L-cut into B-roll (voice leads, picture follows) |
| 8.0-12.0 | Value beat 2: cuts 1.2-1.8s. No cut gap >2.5s |
| 12.0-16.0 | LIST card appears (redacted) — whoosh, music swell |
| 16.0-24.0 | Value beat 3 + proof: FASTEST cuts 1.0-1.5s |
| 24.0-27.0 | REVEAL — ding + impact (LOUDEST moment), music peak, card un-redacts |
| 27.0-34.0 | Before/After card + final value: cuts slow 1.5-2s |
| 34.0-38.0 | Payoff + loop line "and that is because...": slowest cuts 2s, music starts fading |
| 38.0-40.0 | Final beat on clean frame → 0.5s dip-to-dark → audio fade-out completes inside |

## 10. YOUR VIDEO vs PRO — THE GAP LIST (what the next upgrade implements)
1. **5.5s cut stall (4.7→10.2s)** — cap all gaps at 2.5s (adaptive pacing needs a max-gap guard)
2. **Card too early (12% mark)** — move card to 30-45% mark, reveal to 60-70%
3. **Raw TTS voice** — add the 7-step voice chain (HPF→EQ→comp→de-ess→air→saturation→glue)
4. **Flash on every cut** — reserve light-leak for 3 moments (hook→content, reveal, ending)
5. **Muddy ending** — clean final beat + 0.5s dip-to-dark + audio fade inside it
6. **No J/L cuts** — add 1-2 L-cuts mid-video (voice leads B-roll changes)
7. **Flat music intro** — beat-locked intro swell before first word
8. **SFX on cuts not words** — snap SFX to spoken power-word timestamps (VTT)
9. (Optional) 3-4 frame hard-soft polish on the 2-3 roughest cut points
