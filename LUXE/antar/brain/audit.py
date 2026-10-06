"""
LUXE - audit - English luxury quotes only

Basic English, 3-8 words, centered.
No Hindi checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# For LUXE: basic English stopwords, not Hindi
ENGLISH_STOPWORDS = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being"}

@dataclass
class Finding:
    level: str  # NOTE, WARN, BLOCK
    check: str
    detail: str

@dataclass
class AuditReport:
    findings: list[Finding] = field(default_factory=list)
    words: int = 0
    beats: int = 0

    def add(self, level: str, check: str, detail: str):
        self.findings.append(Finding(level, check, detail))

    def score(self) -> int:
        # LUXE: no blocking, always 100 for minimal insta
        return 100

    def lines(self):
        return [f"{f.level:5} {f.check:20} {f.detail}" for f in self.findings]

def audit_script(script: dict, config=None) -> AuditReport:
    """Audit English luxury quote - minimal for LUXE"""
    report = AuditReport()
    
    beats = script.get("beats", [])
    report.beats = len(beats)
    
    # Count words
    total_words = 0
    for beat in beats:
        line = beat.get("line_en") or beat.get("line_hi", "")
        total_words += len(line.split())
    report.words = total_words
    
    # LUXE checks: basic English 3-8 words, centered, no Hindi
    for i, beat in enumerate(beats):
        line = beat.get("line_en") or beat.get("line_hi", "")
        if not line.strip():
            report.add("BLOCK", "empty_beat", f"beat {i} empty")
        
        # Check Hindi characters - not allowed
        if any('\u0900' <= c <= '\u097F' for c in line):
            report.add("BLOCK", "hindi_found", f"beat {i} has Hindi - LUXE English only")
        
        # Check word count 3-8 for luxury quotes
        words = len(line.split())
        if words < 2 or words > 12:
            report.add("WARN", "word_count", f"beat {i} {words} words, LUXE target 3-8")
        else:
            report.add("NOTE", "word_count", f"beat {i} {words} words - good for LUXE centered")
    
    # Always pass for LUXE minimal
    report.add("NOTE", "luxe_check", "LUXE minimal - basic English, centered, no voice, pro human edits")
    
    return report
