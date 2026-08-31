# -*- coding: utf-8 -*-
"""Round 47 guards: agreement cannot be scored off silence.

The third finding from the zero-pole sweep (rounds 45-46). convergence_
index mapped zero confidence volatility to an agreeing +1 signal
unconditionally. Zero volatility among recorded tags is measured
stability; zero volatility with no tags in the window is an absent
signal. An unlabelled, risk-free window therefore converged to 100
off silence alone and the fusion layer awarded "high signal
convergence +5" — agreement no dimension had actually asserted. The
volatility dimension now joins the table only when the window carries
confidence tags, so an all-absent window falls through to the neutral
50 every unmeasured input already gets. The fact layer shares the
detector, so both layers fall silent together (round 30's convention).
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def seam(i, **kw):
    row = {"t": 1000000 + i * 600,
           "next": "dom%d: act on item %d" % (i, i),
           "verified": 0, "open": 0, "marker": "STEP",
           "confidence": "", "verifier": "v%d" % i,
           "risk": "", "error": "", "outcome": "",
           "extra_steps": 0}
    row.update(kw)
    return row


class ConvergenceSilenceTests(unittest.TestCase):

    def test_all_absent_window_is_neutral(self):
        h = [seam(i) for i in range(mindseam.STALL_RUN)]
        self.assertEqual(mindseam.convergence_index(h), 50)

    def test_silent_window_earns_no_convergence_bonus(self):
        h = [seam(i) for i in range(mindseam.STALL_RUN * 2)]
        _, reasons = mindseam.session_health_score(h)
        self.assertFalse(
            any("signal convergence" in r for r in reasons), reasons)

    def test_fact_layer_stays_silent_too(self):
        h = [seam(i) for i in range(mindseam.STALL_RUN * 2)]
        facts = mindseam.observations(h)
        self.assertFalse(
            any("strongly aligned" in f for f in facts), facts)

    def test_recorded_low_risk_still_converges(self):
        # A real signal (risk asserted) may still carry the bonus.
        h = [seam(i, risk="low") for i in range(mindseam.STALL_RUN)]
        self.assertGreaterEqual(mindseam.convergence_index(h), 75)
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("high signal convergence" in r for r in reasons), reasons)

    def test_tagged_flat_confidence_still_counts_as_stable(self):
        # Tags present and never changed: the +1 is measured stability.
        h = [seam(i, confidence="strong", risk="low")
             for i in range(mindseam.STALL_RUN)]
        self.assertGreaterEqual(mindseam.convergence_index(h), 75)

    def test_tagged_oscillation_still_diverges(self):
        h = [seam(i, confidence=c, risk="low")
             for i, c in enumerate(["strong", "shaky", "strong", "shaky"])]
        h = h[-mindseam.STALL_RUN:]
        self.assertLess(mindseam.convergence_index(h), 75)


if __name__ == "__main__":
    unittest.main()
