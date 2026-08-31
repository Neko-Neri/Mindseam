# -*- coding: utf-8 -*-
"""Round 26 guards: an error that was never recovered reads as slow.

error_recovery_speed initialised its backward scan so that an error with
no subsequent recovery scored the same 75/100 as an error recovered on
the very next step — while its docstring promised that unresolved errors
"return low scores". An unresolved error now costs the scale's worst
delay (the zero point), so never-recovered reads strictly worse than
slowly-recovered.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def row(i, error="", verified=0, outcome=""):
    return {"t": 1000 + i, "next": "dom: act %d" % i, "verified": verified,
            "open": 0, "marker": "OPEN", "confidence": "strong",
            "verifier": "v", "risk": "low", "error": error,
            "outcome": outcome, "extra_steps": 0}


class RecoverySpeedTests(unittest.TestCase):

    def test_no_errors_score_100(self):
        self.assertEqual(mindseam.error_recovery_speed(
            [row(0, verified=1), row(1, verified=1)]), 100)

    def test_next_step_recovery_is_fast(self):
        h = [row(0, error="db: down"), row(1, verified=1, outcome="ok")]
        self.assertGreaterEqual(mindseam.error_recovery_speed(h), 75)

    def test_never_recovered_reads_slower_than_next_step(self):
        unresolved = [row(0, verified=1, outcome="ok"), row(1, error="db: down")]
        resolved = [row(0, error="db: down"), row(1, verified=1, outcome="ok")]
        self.assertLess(
            mindseam.error_recovery_speed(unresolved),
            mindseam.error_recovery_speed(resolved),
            "an unresolved trailing error must not read as recovered")

    def test_all_errors_never_recovered_scores_zero(self):
        h = [row(i, error="db: down %d" % i) for i in range(4)]
        self.assertEqual(mindseam.error_recovery_speed(h), 0)

    def test_slow_recovery_still_scores_between(self):
        h = [row(0, error="db: down"), row(1), row(2),
             row(3, verified=1, outcome="ok")]
        score = mindseam.error_recovery_speed(h)
        self.assertGreater(score, 0)
        self.assertLess(score, 100)

    def test_fusion_penalty_reaches_the_reasons(self):
        h = [row(0, verified=1, outcome="ok"),
             row(1, verified=2, outcome="ok"),
             row(2, error="db: down")]
        score, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("error recovery" in r for r in reasons), reasons)


if __name__ == "__main__":
    unittest.main()
