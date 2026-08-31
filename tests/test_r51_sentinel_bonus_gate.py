# -*- coding: utf-8 -*-
"""Round 11 guards: sentinel-100 must never earn a bonus.

Ledger-dependent detectors (ledger_stasis_detector, goal_alignment_score)
return a sentinel 100 when the thing they measure is absent (no book, no
Goal line). The penalty faces are safe — a sentinel can never be < 30 —
and heal_actions gates them behind ``if book is not None``. But the
fusion bonus face consumed the sentinel as if it were measured
perfection: a session with no ledger was awarded "ledger plan alignment
+3" and "high goal alignment +5" for aligning with plans that do not
exist.

These tests pin the corrected contract: unmeasurable factors are silent
in every output face.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def seam(i):
    return {"t": 1000000 + i * 600,
            "next": "task%d:act" % i,
            "verified": i, "open": 1, "marker": "OPEN",
            "confidence": "strong", "verifier": "v%d" % i, "risk": "low",
            "error": "", "outcome": "", "extra_steps": 0}


def healthy_history(n=4):
    return [seam(i) for i in range(n)]


class R51SentinelBonusGateTests(unittest.TestCase):
    """A bonus may only cite a factor that was actually measured."""

    def test_no_ledger_no_plan_alignment_bonus(self):
        _, reasons = mindseam.session_health_score(healthy_history())
        labels = " | ".join(reasons)
        self.assertNotIn("ledger plan alignment", labels)
        self.assertNotIn("ledger plan divergence", labels)

    def test_no_goal_no_goal_alignment_bonus_or_penalty(self):
        _, reasons = mindseam.session_health_score(healthy_history())
        labels = " | ".join(reasons)
        self.assertNotIn("high goal alignment", labels)
        self.assertNotIn("low goal alignment", labels)

    def test_with_goal_and_plan_both_faces_stay_live(self):
        book = {"Goal": "ship the parser",
                "Next": "parser: continue",
                "Open": ["parser: finish edge cases"]}
        h = healthy_history()
        score, reasons = mindseam.session_health_score(h, book=book)
        labels = " | ".join(reasons)
        self.assertIn("goal alignment", labels)
        self.assertTrue(
            any("ledger plan" in r for r in reasons),
            "with a real Next and diverging actions the factor must speak")

    def test_observations_never_cites_unmeasured_factors(self):
        facts = mindseam.observations(healthy_history())
        joined = " ".join(facts).lower()
        self.assertNotIn("plan alignment", joined)
        self.assertNotIn("high goal alignment", joined)

    def test_heal_gates_ledger_detectors_behind_book_presence(self):
        actions = mindseam.heal_actions(healthy_history())
        joined = " | ".join(actions)
        self.assertNotIn("diverge from open ledger thread", joined)
        self.assertNotIn("diverge from the ledger plan", joined)


if __name__ == "__main__":
    unittest.main()
