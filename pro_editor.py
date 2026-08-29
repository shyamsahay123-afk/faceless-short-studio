# ==============================================================================
# PRO EDITOR BRAIN — the AI editor's decision core
# 7 passes: Paper Cut (beat map + tension) → Assembly → Rhythm (cut-on-word,
# tension-based shot lengths, breathing pattern) → Picture Lock → Audio
# (7-step voice chain + music arc + loudness) → Color (primary correction)
# → Graphics → QC.
# Research basis: "Cutting Rhythms" (Pearlman), pro post workflows,
# shot grammar (180/30/20 rules), 2026 mixing standards (-14 LUFS).
# ==============================================================================
import os
import math
import wave
import random
import numpy as np


# ==============================================================================
# PASS 0 — PAPER CUT: beat map with tension levels (story before footage)
# ==============================================================================
def build_beat_map(duration, climax_t=None):
    """Beat map = list of (start, end, tension, name). Tension 1-5.
    tension 5 = climax (loudest, fastest), 2 = loop tail (slowest)."""
    if climax_t is None or climax_t <= 3.0:
        climax_t = duration * 0.65
    hook_end = min(3.0, duration * 0.25)
    climax_start = max(hook_end, climax_t - 1.5)
    climax_end = min(duration, climax_t + 2.5)
    payoff_end = max(climax_end, duration * 0.85)
    beats = [
        (0.0, hook_end, 4, "HOOK"),
        (hook_end, climax_start, 3, "VALUE"),
        (climax_start, climax_end, 5, "CLIMAX"),
        (climax_end, payoff_end, 3, "PAYOFF"),
        (payoff_end, duration, 2, "LOOP"),
    ]
    return [b for b in beats if b[1] - b[0] > 0.3]


def tension_at(beat_map, t):
    best = 3
    for s, e, tension, _name in beat_map:
        if s <= t < e and tension > best:
            best = tension
    return best


# ==============================================================================
# PASS 2 — RHYTHM: the pro's heart
# tension-based shot lengths + 2.5s hard cap + 2-fast-then-slow breathing
# + every cut snapped to a spoken word boundary (cut-on-word)
# ==============================================================================
def snap_to_word(t, vtt_subs, window=0.28):
    """Snap a cut point to the nearest spoken word start (cut ON the word)."""
    best, best_d = t, window
    for s in vtt_subs:
        d = abs(s['start'] - t)
        if d < best_d:
            best, best_d = s['start'], d
    return best


def build_scene_rhythm(beat_map, vtt_subs, duration, seed=7):
    """Returns (start, end) scene boundaries edited with pro rhythm rules."""
    rng = random.Random(seed)

    def cut_len(t):
        if t < 3.0:
            return rng.uniform(0.9, 1.1)          # hook zone: fastest, 3 cuts
        tension = tension_at(beat_map, t)
        if tension >= 5:
            return rng.uniform(1.0, 1.3)          # climax: fast
        if tension >= 4:
            return rng.uniform(1.1, 1.5)
        if tension >= 3:
            return rng.uniform(1.4, 1.9)          # value: medium
        return rng.uniform(1.8, 2.4)              # loop tail: slow

    boundaries = []
    t, fast_streak = 0.0, 0
    while t < duration - 0.3:
        L = cut_len(t)
        if L < 1.3:
            fast_streak += 1
        else:
            fast_streak = 0
        # breathing: after 2 fast cuts, force a slower one (tension-release)
        if fast_streak >= 2:
            L = max(L, 1.9)
            fast_streak = 0
        L = min(L, 2.5)                            # HARD CAP: no stall > 2.5s
        end = min(t + L, duration)
        end = snap_to_word(end, vtt_subs)          # cut ON the spoken word
        if end - t >= 0.45:
            boundaries.append((t, end))
        t = end
    if not boundaries:
        boundaries = [(0.0, duration)]
    return boundaries


# ==============================================================================
# PASS 4a — VOICE CHAIN (the 7-step pro chain, real DSP in numpy)
# HPF → subtractive EQ ×2 → compressor → de-esser → air → saturation
# ==============================================================================
def _read_wav(path):
    with wave.open(path, 'rb') as w:
        sr = w.getframerate()
        nch = w.getnchannels()
        raw = w.readframes(w.getnframes())
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    if nch > 1:
        x = x.reshape(-1, nch).mean(axis=1)
    return x, sr


def _write_wav(path, x, sr):
    x = np.clip(x, -0.995, 0.995)
    data = (x * 32767).astype(np.int16).tobytes()
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data)


def _one_pole_hpf(x, fc, sr):
    rc = 1.0 / (2.0 * math.pi * fc)
    dt = 1.0 / sr
    a = rc / (rc + dt)
    y = np.empty_like(x)
    yp = xp = 0.0
    for i in range(len(x)):
        y[i] = a * (yp + x[i] - xp)
        yp, xp = y[i], x[i]
    return y


def _biquad_peaking(x, fc, db, q, sr):
    w0 = 2.0 * math.pi * fc / sr
    cw, sw = math.cos(w0), math.sin(w0)
    A = 10.0 ** (abs(db) / 40.0)
    alpha = sw / (2.0 * q)
    if db < 0:
        b0, b2 = 1.0 - alpha * A, 1.0 + alpha * A
    else:
        b0, b2 = 1.0 + alpha * A, 1.0 - alpha * A
    b1 = -2.0 * cw
    a0, a1, a2 = 1.0 + alpha, -2.0 * cw, 1.0 - alpha
    b0, b1, b2, a1, a2 = b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0
    y = np.empty_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i in range(len(x)):
        xi = x[i]
        yi = b0 * xi + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        y[i] = yi
        x2, x1 = x1, xi
        y2, y1 = y1, yi
    return y


def _compressor(x, threshold_db, ratio, attack_s, release_s, sr):
    """Feedforward gain-cell style compressor."""
    thresh = 10.0 ** (threshold_db / 20.0)
    a_atk = math.exp(-1.0 / (attack_s * sr))
    a_rel = math.exp(-1.0 / (release_s * sr))
    y = np.empty_like(x)
    env = 0.0
    for i in range(len(x)):
        ax = abs(x[i])
        env = a_atk * env + (1 - a_atk) * ax if ax > env else a_rel * env + (1 - a_rel) * ax
        if env > thresh:
            excess = env - thresh
            out_amp = thresh + excess / ratio
            gain = out_amp / env
        else:
            gain = 1.0
        y[i] = x[i] * gain
    return y


def _de_ess(x, sr, f0=3000.0, f1=5500.0, thresh=0.075, cut_db=6.0):
    """FFT-band de-esser with 50%-overlap Hann OLA (length-preserving)."""
    n = len(x)
    block = 4410
    hop = block // 2
    n_blocks = (n - block) // hop + 1
    if n_blocks <= 0:
        return x
    out = np.zeros(n + block)
    win_sum = np.zeros(n + block)
    hann = np.hanning(block)
    f = np.fft.rfftfreq(block, 1.0 / sr)
    band = (f >= f0) & (f <= f1)
    cut = 10.0 ** (-cut_db / 20.0)
    for b in range(n_blocks):
        seg = x[b * hop: b * hop + block]
        if seg is None or len(seg) < block:
            break
        X = np.fft.rfft(seg * hann)
        band_rms = float(np.sqrt(np.mean(np.abs(X[band]) ** 2)) / block)
        if band_rms > thresh:
            X[band] *= cut
        out[b * hop: b * hop + block] += np.fft.irfft(X, block) * hann
        win_sum[b * hop: b * hop + block] += hann * hann
    safe = np.where(win_sum > 1e-6, win_sum, 1.0)
    result = (out / safe)[:n]
    # blend edges (OLA edges fade) with the original
    edge = min(block, n // 10)
    fade = np.linspace(0, 1, edge)
    result[:edge] = x[:edge] * (1 - fade) + result[:edge] * fade
    result[-edge:] = x[-edge:] * (1 - fade) + result[-edge:] * fade
    return result


def apply_voice_chain(audio_path, out_dir=None):
    """Full 7-step pro voice chain. Returns processed wav path."""
    if out_dir is None:
        out_dir = os.path.dirname(audio_path) or "."
    out_path = os.path.join(out_dir, "voice_chain_processed.wav")
    try:
        in_wav = audio_path
        if not audio_path.lower().endswith(".wav"):
            # TTS outputs MP3 — convert to WAV first (voice chain is WAV-based)
            in_wav = os.path.join(out_dir, "voice_chain_input.wav")
            import subprocess
            try:
                import imageio_ffmpeg
                _ff = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                _ff = "ffmpeg"
            subprocess.run([_ff, "-y", "-loglevel", "error", "-i", audio_path,
                            "-ac", "1", "-ar", "44100", in_wav], check=True, timeout=120)
        x, sr = _read_wav(in_wav)
        if len(x) < sr // 4:
            return audio_path
        x = _one_pole_hpf(x, 90.0, sr)                      # 1. HPF rumble
        x = _biquad_peaking(x, 300.0, -2.5, 1.0, sr)        # 2a. murmur cut
        x = _biquad_peaking(x, 5000.0, -2.0, 1.2, sr)       # 2b. harshness cut
        x = _compressor(x, -18.0, 3.0, 0.010, 0.150, sr)    # 3. tone compressor
        x = _de_ess(x, sr)                                   # 4. de-esser
        x = _biquad_peaking(x, 10000.0, 2.0, 0.7, sr)       # 5. air (presence shelf)
        x = np.tanh(1.35 * x) / np.tanh(1.35)                # 6. warmth saturation
        x = _compressor(x, -14.0, 1.5, 0.020, 0.200, sr)    # 7. glue
        # final: normalize toward ~-14 LUFS so every video's voice sits at
        # the same level (consistency across the channel)
        rms = float(np.sqrt(np.mean(x ** 2)))
        if rms > 1e-4:
            g = min(0.063 / rms, 2.0)
            x = np.tanh(x * g / 0.95) * 0.95
        _write_wav(out_path, x, sr)
        return out_path
    except Exception as e:
        print(f"[ProEditor] voice chain failed ({e}); using raw voice")
        return audio_path


# ==============================================================================
# PASS 4b — MUSIC: beat-locked intro swell + asymmetric voice duck (breathing)
# + climax peak + outro fade
# ==============================================================================
def voice_duck_curve(vtt_subs, duration, sr_grid=50.0):
    """Music gain grid (50Hz): full in gaps, -55% under speech.
    Asymmetric smoothing: fast attack (50ms), slow release (400ms) = breathing."""
    n = int(duration * sr_grid) + 2
    raw = np.zeros(n)
    dt = 1.0 / sr_grid
    # mark every spoken-word window (vectorized interval fill)
    for s in vtt_subs:
        i0 = max(0, int((s['start'] - 0.08) * sr_grid))
        i1 = min(n - 1, int((s['end'] + 0.15) * sr_grid))
        if i1 >= i0:
            raw[i0:i1 + 1] = np.maximum(raw[i0:i1 + 1], 0.55)
    # asymmetric EMA smoothing
    d = np.zeros(n)
    a_up = 1.0 - math.exp(-dt / 0.05)     # fast when duck starts
    a_dn = 1.0 - math.exp(-dt / 0.40)     # slow when duck releases
    for i in range(1, n):
        if raw[i] > d[i - 1]:
            d[i] = d[i - 1] + a_up * (raw[i] - d[i - 1])
        else:
            d[i] = d[i - 1] + a_dn * (raw[i] - d[i - 1])
    gain = 1.0 - d
    # intro: confident swell 0-0.6s, then bed level
    for i in range(min(n, int(0.6 * sr_grid))):
        gain[i] = min(1.0, gain[i] + (1.0 - 0.7) * (1 - i / (0.6 * sr_grid)))
    # outro fade: last 1.5s (linear 1.0 -> 0.0)
    outro = int(1.5 * sr_grid)
    if n > outro:
        for i in range(n - outro, n):
            k = max(0.0, (n - i) / outro)
            gain[i] *= k
    return np.clip(gain, 0.0, 1.0)


def music_arc_gain(t, climax_t, duck_grid, sr_grid=50.0):
    """Combined music gain: base arc (40% → build → 100% at climax → 40%)
    × voice duck grid (breathing under speech)."""
    if t < 2.5:
        base = 0.4 * (t / 2.5)
    else:
        build_end = max(4.0, climax_t - 2.0)
        if t < build_end:
            base = 0.4 + 0.35 * (t - 2.5) / max(0.1, build_end - 2.5)
        elif t < climax_t:
            base = 0.75 + 0.25 * (t - build_end) / max(0.1, climax_t - build_end)
        elif t < climax_t + 1.5:
            base = 1.0 - 0.6 * ((t - climax_t) / 1.5)
        else:
            base = 0.4
    if duck_grid is not None:
        i = min(len(duck_grid) - 1, max(0, int(t * sr_grid)))
        base *= duck_grid[i]
    return base


# ==============================================================================
# PASS 4c — LOUDNESS: normalize final mix toward -14 LUFS (RMS approx) + soft clip
# ==============================================================================
def normalize_loudness(audio_path, out_dir=None):
    """Simple K-weighting-free RMS normalization to ~-14 LUFS + tanh safety."""
    if out_dir is None:
        out_dir = os.path.dirname(audio_path) or "."
    out_path = os.path.join(out_dir, "final_mix_normalized.wav")
    try:
        x, sr = _read_wav(audio_path)
        rms = float(np.sqrt(np.mean(x ** 2)))
        if rms < 1e-4:
            return audio_path
        target = 0.063   # ≈ -14 LUFS for speech RMS
        gain = target / rms
        gain = min(gain, 3.0)   # never boost > +9.5dB
        x = x * gain
        x = np.tanh(x / 0.97) * 0.97   # soft limiter
        _write_wav(out_path, x, sr)
        return out_path
    except Exception as e:
        print(f"[ProEditor] loudness normalize failed ({e})")
        return audio_path


# ==============================================================================
# PASS 5 — COLOR: primary correction (per-clip exposure match)
# ==============================================================================
def exposure_gain_for_frames(frames):
    """Given a few sampled frames, return a gain that matches them to target
    luminance (primary correction — makes all clips expose consistently)."""
    lums = []
    for f in frames:
        if f is not None:
            a = f.astype(np.float32)
            lums.append(0.2126 * a[..., 0].mean() + 0.7152 * a[..., 1].mean() + 0.0722 * a[..., 2].mean())
    if not lums:
        return 1.0
    lum = float(np.mean(lums))
    target = 46.0   # dark-premium target luminance
    g = target / max(lum, 6.0)
    return float(np.clip(g, 0.82, 1.55))


# ==============================================================================
# PASS 7 — QC: luminance floor sweep
# ==============================================================================
def qc_luminance_sweep(clip, duration, step=1.0):
    """Sample frames across the timeline; report min mean luminance."""
    min_lum = 255.0
    worst_t = 0.0
    t = 0.0
    while t < duration - 0.2:
        try:
            f = clip.get_frame(t)
            lum = float(f.mean())
            if lum < min_lum:
                min_lum, worst_t = lum, t
        except Exception:
            pass
        t += step
    ok = min_lum >= 8.0
    print(f"[QC] luminance sweep: min={min_lum:.1f} at t={worst_t:.1f}s -> {'PASS' if ok else 'WARN: frame near-black'}")
    return ok
