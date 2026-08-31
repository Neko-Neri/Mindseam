# -*- coding: utf-8 -*-
"""Round 59 guards: the convergence-index decision table.

convergence_index reads four signals off the window — risk level,
confidence, momentum, volatility — and scores their agreement. The
fusion layer adds +5 at 75+ and −5 below 30, and the fact layer prints
"strongly aligned" / "strongly divergent" at the same edges. The table
pins the aligned, divergent and neutral shapes plus the short-window
neutral 50.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def hist(n=3, risk="low", conf="strong", verifieds=None):
    if verifieds is None:
        verifieds = list(range(1, n + 1))
    return [{"t": 1000 + i, "next": "dom: act %d" % i, "verified": v,
             "open": 0, "marker": "OPEN", "confidence": conf,
             "verifier": "v", "risk": risk, "error": "",
             "outcome": "ok", "extra_steps": 0}
            for i, v in enumerate(verifieds)]


class ConvergenceTableTests(unittest.TestCase):

    def test_aligned_signals_score_high(self):
        # low risk + strong confidence + positive momentum + flat
        # confidence = full agreement.
        score = mindseam.convergence_index(hist())
        self.assertGreaterEqual(score, 75)

    def test_divergent_signals_score_low(self):
        # shaky confidence + rising verification = disagreement.
        score = mindseam.convergence_index(
            hist(conf="shaky", verifieds=[1, 2, 3]))
        self.assertLess(score, 30)

    def test_short_window_is_neutral_fifty(self):
        self.assertEqual(mindseam.convergence_index(hist(n=2)), 50)

    def test_fusion_factor_follows_the_table(self):
        _, reasons = mindseam.session_health_score(hist())
        self.assertTrue(
            any("high signal convergence" in r for r in reasons), reasons)

    def test_fact_band_matches_the_fusion_band(self):
        facts = mindseam.observations(hist())
        self.assertTrue(
            any("strongly aligned" in f for f in facts), facts)


if __name__ == "__main__":
    unittest.main()
