# ==============================================================================
# RETENTION ENGINE — "the app learns from your viewers"
# 1. parse_retention_csv  : YouTube Studio "Average Percentage of Viewers" export
#                           (robust to the 3 column layouts YT has shipped)
# 2. find_retention_dips  : where the curve drops and stays dropped
# 3. recut_script_for_dips: whole sentences inside a dip are CUT from the script
#                           -> re-render = shorter video, no dead zone.
# Pro rule: you never cut mid-sentence. You cut the THOUGHT the audience left on.
# ==============================================================================
import os
import re
import csv
import io


def _parse_time_cell(s):
    """'1:23' -> 83.0 | '0:01:02' -> 62.0 | '83' / '83.5' -> seconds. None on fail."""
    s = str(s).strip().replace(",", ".")
    if not s:
        return None
    if ":" in s:
        parts = s.split(":")
        if len(parts) == 2:
            try:
                return int(float(parts[0])) * 60 + float(parts[1])
            except ValueError:
                return None
        if len(parts) == 3:
            try:
                return int(float(parts[0])) * 3600 + int(float(parts[1])) * 60 + float(parts[2])
            except ValueError:
                return None
        return None
    try:
        v = float(s)
        return v if v >= 0 else None
    except ValueError:
        return None


def _parse_pct_cell(s):
    s = str(s).strip().rstrip("%").replace(",", ".")
    if not s:
        return None
    try:
        v = float(s)
        return v if 0 <= v <= 100 else None
    except ValueError:
        return None


def parse_retention_csv(path_or_text):
    """Return sorted [(t_seconds, pct)] from a YouTube Studio retention export.
    Accepts the file path or the raw CSV text. Handles:
      - 'Time watched' / 'Audience retention' (either order, with or without %)
      - m:ss | h:mm:ss | float-seconds time cells
      - BOM, CRLF, header row present or absent
    """
    s = str(path_or_text)
    looks_like_path = ("\n" not in s and len(s) < 300) and (
        s.lower().endswith((".csv", ".txt")) or os.path.exists(s))
    if looks_like_path:
        with open(s, "r", encoding="utf-8-sig", errors="replace") as f:
            raw = f.read()
    else:
        raw = s

    all_rows = [[c.strip() for c in row[:4]] for row in csv.reader(io.StringIO(raw)) if len(row) >= 2]
    if not all_rows:
        return []

    # header-aware column detection (rows where both cells are bare numbers are
    # ambiguous otherwise) — only the FIRST row counts as a header if it actually
    # contains column names
    time_col = pct_col = None
    data_rows = all_rows
    lowered = [c.lower() for c in all_rows[0]]
    for i, c in enumerate(lowered):
        if time_col is None and re.search(r"time|watched|^t$|sec|min:sec|minute", c):
            time_col = i
        if pct_col is None and re.search(r"pct|percent|retention|audience", c):
            pct_col = i
    if (time_col is not None and pct_col is not None) or any(
            re.search(r"time|watched|pct|percent|retention", c) for c in lowered):
        data_rows = all_rows[1:]

    rows = []
    for cells in data_rows:
        if time_col is not None and pct_col is not None and \
                time_col < len(cells) and pct_col < len(cells):
            t = _parse_time_cell(cells[time_col])
            p = _parse_pct_cell(cells[pct_col])
            if t is not None and p is not None and p <= 100:
                rows.append((t, p))
            continue
        pcts = [(i, _parse_pct_cell(c)) for i, c in enumerate(cells)]
        times = [(i, _parse_time_cell(c)) for i, c in enumerate(cells)]
        # unambiguous cells first: % marks pct, : marks time
        pi = next((i for i, v in pcts if v is not None and "%" in cells[i]), None)
        ti = next((i for i, v in times if v is not None and (":" in cells[i] or i != pi)), None)
        if pi is None or ti is None or pi == ti:
            # all bare numbers: default order = (time, pct) — YT's default export
            ti, pi = 0, 1
        p, t = pcts[pi][1], times[ti][1]
        if p is None or t is None or p > 100:
            continue
        rows.append((t, p))

    rows.sort(key=lambda x: x[0])
    # de-duplicate on time (keep last)
    dedup = {}
    for t, p in rows:
        dedup[round(t, 2)] = p
    curve = sorted(dedup.items())
    return curve


def _smooth(values, window=3):
    out = []
    for i in range(len(values)):
        lo = max(0, i - window // 2)
        hi = min(len(values), i + window // 2 + 1)
        out.append(sum(values[lo:hi]) / max(1, hi - lo))
    return out


def find_retention_dips(curve, min_drop=12.0, min_dur=1.5, max_dips=5):
    """curve: [(t, pct)]. Returns list of dicts:
    {start, end, depth_pct, min_pct} — biggest sustained drops first.

    Algorithm (pro rule): a dip = the curve drops >= min_drop points below the
    LOCAL LEVEL (the audience that was still there), and then SETTLES at the new
    lower level (or the video ends low). The 0-2.5s hook drop is structure,
    never a dip — viewers decide in 2-3s; that's a hook problem, not content."""
    if len(curve) < 4:
        return []
    ts = [t for t, _ in curve]
    ps = _smooth([p for _, p in curve])
    n = len(ps)

    base_i = 1
    while base_i < n and ts[base_i] < 2.5:
        base_i += 1

    # anchor = expected local level. It re-anchors when the curve settles at a
    # LOWER, flat level for 3 consecutive points (the audience that stayed
    # becomes the new baseline). Gradual attrition re-anchors continuously and
    # therefore never registers as a dip — only sharp cluster-leaving does.
    anchor = ps[base_i]
    deficit = [0.0] * n
    for i in range(base_i, n):
        deficit[i] = anchor - ps[i]
        if i >= base_i + 2:
            a, b, c = ps[i - 2], ps[i - 1], ps[i]
            if max(a, b, c) - min(a, b, c) <= 2.5 and (anchor - ps[i]) > min_drop:
                anchor = ps[i]

    in_dip = [deficit[i] >= min_drop for i in range(n)]
    dips = []
    i = base_i
    while i < n:
        if not in_dip[i]:
            i += 1
            continue
        j = i
        while j < n and in_dip[j]:
            j += 1
        run_a, run_b = ts[i], ts[j - 1]
        # accept: the low zone lasts >= 1s (sub-second blips are export jitter)
        if (run_b - run_a) >= min(1.0, min_dur):
            dips.append({
                "start": run_a, "end": run_b,
                "depth_pct": round(max(deficit[i:j]), 1),
                "min_pct": round(min(ps[i:j]), 1),
            })
        i = j
    dips.sort(key=lambda d: -d["depth_pct"])
    return dips[:max_dips]


def _sentences_from_subs(vtt_subs, gap=0.35):
    """Group word-level cues into spoken sentences [(t0, t1, [words])]."""
    if not vtt_subs:
        return []
    sents = []
    cur_words = [vtt_subs[0]["text"]]
    cur_start = vtt_subs[0]["start"]
    cur_end = vtt_subs[0]["end"]
    for s in vtt_subs[1:]:
        if s["start"] - cur_end > gap:
            sents.append((cur_start, cur_end, cur_words))
            cur_words = [s["text"]]
            cur_start, cur_end = s["start"], s["end"]
        else:
            cur_words.append(s["text"])
            cur_end = s["end"]
    sents.append((cur_start, cur_end, cur_words))
    return sents


def recut_script_for_dips(script_text, vtt_subs, dips, pad=0.4, protect_first=True, protect_last=True):
    """Cut whole SPOKEN SENTENCES that fall inside a dip window from the script.
    Never cuts mid-sentence; never cuts the hook (first line) or the CTA (last
    bracket line). Returns (new_script, removed:[(t0,t1,sentence_text)])."""
    if not dips or not vtt_subs:
        return script_text, []

    # expand dip windows with pad, merge overlaps
    wins = sorted([(d["start"] - pad, d["end"] + pad) for d in dips])
    merged = []
    for a, b in wins:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))

    def in_dip(t0, t1):
        for a, b in merged:
            overlap = min(t1, b) - max(t0, a)
            if overlap > 0.5 * (t1 - t0):
                return True
        return False

    sents = _sentences_from_subs(vtt_subs)
    removed_keys = set()   # normalized sentence text (lowercase, no punct)
    for t0, t1, words in sents:
        if in_dip(t0, t1):
            key = re.sub(r"[^a-z0-9\u0900-\u097F]", "", " ".join(w.lower() for w in words))
            if key:
                removed_keys.add(key)

    if not removed_keys:
        return script_text, []

    def _norm(t):
        return re.sub(r"[^a-z0-9\u0900-\u097F]", "", t.lower())

    content_idx = 0
    n_content = sum(0 for l in str(script_text).split("\n")
                    if l.strip() and not (l.strip().startswith("[") and l.strip().endswith("]")))
    new_lines = []
    removed = []
    for line in str(script_text).split("\n"):
        ls = line.strip()
        is_content = bool(ls) and not (ls.startswith("[") and ls.endswith("]"))
        if not is_content:
            new_lines.append(line)
            continue
        is_first = (content_idx == 0)
        is_last = (content_idx == n_content - 1)
        content_idx += 1
        # split the line into sentences (keep the delimiter)
        parts = re.split(r"(?<=[\.\!\?])\s+", ls)
        kept = []
        for p in parts:
            key = _norm(p)
            if key and any(key in rk or rk in key and len(rk) > 8 for rk in removed_keys):
                removed.append(p.strip())
                continue
            kept.append(p)
        if is_first and kept and protect_first:
            # hook: restore everything (a dip at 0-3s is structure, not content)
            new_lines.append(line)
            continue
        if is_last and protect_last and (not kept or len(kept) < len(parts)):
            # CTA: keep it whole or not at all — a half CTA is worse than none
            new_lines.append(line if removed and not kept else line)
            continue
        if kept:
            new_lines.append(" ".join(kept) if len(kept) > 1 else kept[0])
    new_script = "\n".join(new_lines).strip()
    return new_script, removed
