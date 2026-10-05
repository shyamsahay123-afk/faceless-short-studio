"""
ANTAR - the script audit.

Every finding here is a number or a position. Nothing is decided by matching
one string against another and calling that a verdict.

A finding has a level:
    BLOCK  the script cannot be used. The writer must try again.
    WARN   usable, but the score drops and the reason is printed.
    NOTE   information only.

The audit is deliberately forgiving about length, because a gate that ends a
run with nothing is a defect. Short is a warning; only a script so short it
cannot fill the video, or so long it cannot fit, is blocked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import objects

# words that are grammar, not content. used by the echo check.
STOPWORDS = {
    "और", "या", "लेकिन", "पर", "वो", "वह", "यह", "ये", "है", "हैं", "था", "थी", "थे",
    "को", "का", "की", "के", "में", "से", "ने", "पर", "भी", "ही", "तो", "जो", "कि",
    "एक", "नहीं", "कुछ", "सब", "तुम", "तुम्हें", "तुम्हारा", "तुम्हारी", "तुम्हारे",
    "मैं", "मुझे", "मेरा", "मेरी", "मेरे", "हम", "अपना", "अपनी", "अपने", "जब", "तब",
    "क्यों", "कैसे", "क्या", "इस", "उस", "इसलिए", "वही", "फिर", "अब", "आज",
}


@dataclass
class Finding:
    level: str
    check: str
    detail: str
    value: object = None
    index: int = -1


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    words: int = 0
    beats: int = 0
    objects_found: int = 0
    peak_index: int = -1

    def add(self, level: str, check: str, detail: str, value=None, index: int = -1) -> None:
        self.findings.append(Finding(level, check, detail, value, index))

    @property
    def blocked(self) -> bool:
        return any(f.level == "BLOCK" for f in self.findings)

    def of(self, level: str) -> list[Finding]:
        return [f for f in self.findings if f.level == level]

    def score(self) -> int:
        """
        0-100.

        A blocked script scores 0. Otherwise only WARN costs points: a NOTE is
        information, and an audit that penalises its own notes punishes a
        script for being audited.
        """
        if self.blocked:
            return 0
        return max(0, 100 - 12 * len(self.of("WARN")))

    def lines(self) -> list[str]:
        return [f"{f.level:5} {f.check:18} {f.detail}" for f in self.findings]


def count_words(text: str) -> int:
    """Devanagari word count: split on whitespace, drop bare punctuation."""
    tokens = re.split(r"\s+", text.strip())
    return sum(1 for t in tokens if re.search(r"[\u0900-\u097F0-9A-Za-z]", t))


def content_words(text: str) -> set[str]:
    """Words that carry meaning, for the echo check."""
    tokens = re.split(r"[\s।,.!?;:—\-]+", text)
    out = set()
    for token in tokens:
        clean = token.strip("।,.!?;:—-")
        if len(clean) < 3:
            continue
        if clean in STOPWORDS:
            continue
        out.add(clean)
    return out


IMPERATIVE_MARKERS = ("करो", "मत करो", "कर लो", "देखो", "सुनो", "जाओ", "रुको",
                      "बनो", "कहो", "सोचो", "छोड़ो", "अपनाओ", "पहनो", "बोलो")


def audit(script: dict, floor: int, ceiling: int, band: tuple[int, int] | None = None) -> Report:
    """
    Audit a script dict produced by the writer.

    Expected shape:
        {"title_hi": str, "closing_echo": str, "peak_line": int,
         "beats": [{"line_hi": str, "object_hi": str, "role": str}, ...]}
    """
    report = Report()

    beats = script.get("beats") or []
    if not isinstance(beats, list) or not beats:
        report.add("BLOCK", "structure", "no beats in the script")
        return report

    lines = []
    for i, beat in enumerate(beats):
        if not isinstance(beat, dict):
            report.add("BLOCK", "structure", f"beat {i} is not an object", index=i)
            continue
        line = (beat.get("line_hi") or "").strip()
        if not line:
            report.add("BLOCK", "structure", f"beat {i} has no line", index=i)
        lines.append((i, line, (beat.get("object_hi") or "").strip(), (beat.get("role") or "").strip()))

    if not lines:
        report.add("BLOCK", "structure", "every beat was empty")
        return report

    whole = " ".join(line for _, line, _, _ in lines)
    report.words = count_words(whole)
    report.beats = len(lines)

    # ---------------------------------------------------------- length
    if report.words < floor:
        report.add("BLOCK", "length", f"{report.words} words, floor is {floor} - too short to fill the video",
                   report.words)
    elif report.words > ceiling:
        report.add("BLOCK", "length", f"{report.words} words, ceiling is {ceiling} - will not fit the duration",
                   report.words)
    elif band and not (band[0] <= report.words <= band[1]):
        report.add("WARN", "length", f"{report.words} words, target band is {band[0]}-{band[1]}",
                   report.words)
    else:
        report.add("NOTE", "length", f"{report.words} words, inside the band", report.words)

    # ---------------------------------------------------------- objects
    missing = []
    for i, line, hint, _ in lines:
        found = objects.resolve(line, hint)
        if found:
            report.objects_found += 1
        else:
            missing.append(i)
            report.add("WARN", "object", f"beat {i+1}: nothing a camera can point at", index=i)
    if not missing:
        report.add("NOTE", "object", f"all {report.beats} beats name a filmable object")

    duplicates = _duplicate_objects(lines)
    for i, word in duplicates:
        report.add("NOTE", "object-repeat", f"beat {i+1} reuses '{word}' - variety helps", index=i)

    # ---------------------------------------------------------- voice
    if objects.has_apa(whole):
        report.add("WARN", "address", "आप appears - the lane speaks in तुम", index=-1)
    tum = objects.count_tum(whole)
    if tum == 0:
        report.add("WARN", "address", "तुम never appears - the script is not talking to anyone")
    elif tum < 2:
        report.add("NOTE", "address", f"तुम appears {tum} time - a little thin")
    else:
        report.add("NOTE", "address", f"तुम appears {tum} times")

    names = objects.find_banned_names(whole)
    if names:
        report.add("BLOCK", "names", f"names present: {', '.join(names)} - never allowed")
    else:
        report.add("NOTE", "names", "no names")

    imperatives = [m for m in IMPERATIVE_MARKERS if re.search(rf"\b{m}\b", whole)]
    if imperatives:
        report.add("WARN", "imperative", f"commanding tone: {', '.join(imperatives[:3])}")

    # ---------------------------------------------------------- structure
    if lines:
        first_role = lines[0][3]
        last_role = lines[-1][3]
        if first_role and first_role != "hook":
            report.add("NOTE", "role", f"first beat is '{first_role}', expected 'hook'")
        if last_role and last_role != "payoff":
            report.add("WARN", "role", f"last beat is '{last_role}', expected 'payoff'")

    # the opening line should open something. a question mark or a gap word.
    opening = lines[0][1]
    if not _opens(opening):
        report.add("WARN", "hook", "the first line does not open a question or a gap")

    # ---------------------------------------------------------- peak
    peak = script.get("peak_line")
    report.peak_index = _peak_index(peak, len(lines))
    tail = {len(lines) - 1, len(lines) - 2}
    if report.peak_index == 0 and not isinstance(peak, int):
        report.peak_index = _longest_content_index(lines)
        report.add("NOTE", "peak", "writer did not name a peak; used the heaviest line instead")
    if report.peak_index not in tail:
        report.add("WARN", "peak", f"the strongest line is beat {report.peak_index+1} of {len(lines)} - it belongs in the last two")

    # ---------------------------------------------------------- loop
    closing = (script.get("closing_echo") or "").strip()
    echo_text = closing or lines[-1][1]
    overlap = content_words(echo_text) & content_words(opening)
    ratio = len(overlap) / max(1, len(content_words(opening)))
    if ratio >= 0.30:
        report.add("NOTE", "loop", f"closing line echoes the opening ({len(overlap)} shared words)")
    elif ratio > 0:
        report.add("WARN", "loop", f"closing line barely echoes the opening ({len(overlap)} shared words)")
    else:
        report.add("WARN", "loop", "closing line does not echo the opening - the video will not loop")

    # ---------------------------------------------------------- rhythm
    lengths = [count_words(line) for _, line, _, _ in lines]
    if lengths and max(lengths) > 26:
        report.add("WARN", "rhythm", f"a line runs to {max(lengths)} words - long lines lose the eye")
    if lengths and (max(lengths) - min(lengths)) < 2:
        report.add("NOTE", "rhythm", "line lengths are uniform - the lane asks for uneven rhythm")

    return report


def _opens(line: str) -> bool:
    """Does the first line open a question or a gap, rather than state a fact?"""
    if "?" in line:
        return True
    openers = ("जब", "अगर", "कभी", "हर बार", "तुम्हें लगता", "सच यह", "वो पल",
               "एक दिन", "शायद", "क्या")
    return any(line.strip().startswith(o) for o in openers)


def _peak_index(peak, count: int) -> int:
    if isinstance(peak, int) and 1 <= peak <= count:
        return peak - 1
    if isinstance(peak, str) and peak.strip().isdigit():
        value = int(peak.strip())
        if 1 <= value <= count:
            return value - 1
    return 0


def _longest_content_index(lines) -> int:
    best, best_score = 0, -1
    for i, (_, line, _, _) in enumerate(lines):
        score = len(content_words(line))
        if score > best_score:
            best, best_score = i, score
    return best


def _duplicate_objects(lines) -> list[tuple[int, str]]:
    seen: dict[str, int] = {}
    out: list[tuple[int, str]] = []
    for i, line, hint, _ in lines:
        found = objects.resolve(line, hint)
        if not found:
            continue
        word = found[1]
        if word in seen:
            out.append((i, word))
        else:
            seen[word] = i
    return out
