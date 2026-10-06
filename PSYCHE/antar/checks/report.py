"""
ANTAR - the check suite's own vocabulary.

A check is a number, a target, and a verdict. Nothing in a check is an
opinion, and nothing is allowed to be quietly skipped: a check that cannot be
measured says so, by name, and the report shows it as UNAVAILABLE rather than
turning it into a pass. A silent pass is how a broken video reaches an upload
button.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

BLOCKING = "blocking"
WARNING = "warning"

PASS, WARN, FAIL, UNAVAILABLE = "PASS", "WARN", "FAIL", "UNAVAILABLE"


@dataclass
class Check:
    name: str
    kind: str                 # blocking | warning
    status: str               # PASS | WARN | FAIL | UNAVAILABLE
    measured: str             # the number, phrased for a human
    target: str               # what it was judged against
    detail: str = ""          # evidence, or why it could not be measured

    @property
    def blocking_failure(self) -> bool:
        return self.kind == BLOCKING and self.status == FAIL

    @property
    def passed(self) -> bool:
        return self.status == PASS

    def line(self) -> str:
        return f"{self.status:11} {self.name:34} {self.measured}"

    def as_dict(self) -> dict:
        return {"name": self.name, "kind": self.kind, "status": self.status,
                "measured": self.measured, "target": self.target, "detail": self.detail}


@dataclass
class Report:
    render_id: str
    checks: list[Check] = field(default_factory=list)
    score: dict = field(default_factory=dict)
    bundle: dict = field(default_factory=dict)

    def add(self, check: Check) -> Check:
        self.checks.append(check)
        return check

    @property
    def blocking(self) -> list[Check]:
        return [c for c in self.checks if c.kind == BLOCKING]

    @property
    def warnings(self) -> list[Check]:
        return [c for c in self.checks if c.kind == WARNING]

    @property
    def failed(self) -> list[Check]:
        return [c for c in self.checks if c.status == FAIL]

    @property
    def blocked_from_upload(self) -> bool:
        return bool([c for c in self.checks if c.blocking_failure])

    @property
    def cleared(self) -> bool:
        """True only when every blocking check passed. Warnings never block."""
        return not self.blocked_from_upload

    def unlocks(self) -> tuple[bool, str]:
        """
        The upload decision: every blocking check passed AND the score is 85+.

        If the score cannot be fully measured yet - a category that needs a
        later phase - the decision says so instead of pretending the missing
        points were earned.
        """
        if self.blocked_from_upload:
            worst = ", ".join(c.name for c in self.checks if c.blocking_failure)
            return False, f"blocked by: {worst}"
        withheld = self.score.get("withheld", 0)
        total = self.score.get("total", 0)
        if withheld:
            return False, (f"{withheld} of 100 points cannot be measured yet "
                           f"({', '.join(self.score.get('missing', []))}) - "
                           f"the unlock cannot be judged on {total}/100 measured")
        need = self.score.get("unlock", 85)
        if total >= need:
            return True, f"{total}/100 - at or above the {need} unlock"
        return False, f"{total}/100 - below the {need} unlock"

    def counts(self) -> dict:
        out = {PASS: 0, WARN: 0, FAIL: 0, UNAVAILABLE: 0}
        for check in self.checks:
            out[check.status] = out.get(check.status, 0) + 1
        return out


def write_json(path: Path, payload: dict) -> Path:
    import json
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    temporary.replace(path)
    return path
