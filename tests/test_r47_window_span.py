# -*- coding: utf-8 -*-
"""Round 7 guards for defect 16: window-span lies in fact lines.

observations() collected its facts from the trailing STALL_RUN window
(``run``), but three fact templates interpolated ``len(hist)`` as the
span, so a 6-seam session whose degeneration lived only in the last 3
seams was told apart in the same output: one line said "last 3 seams"
(honest) and the next said "last 6 seams" (a lie — the first 3 seams
were 'strong'). Four more templates hardcoded ``% STALL_RUN``, which
reproduced the same lie under a custom ``run=`` window. All span
interpolations now report the window the facts were actually
collected from.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def step(t, nxt="alpha:step", conf="thin", marker="OPEN", verifier="v1"):
    return {"t": 1000 + t * 600, "next": nxt, "verified": t, "open": 1,
            "marker": marker, "confidence": conf, "verifier": verifier,
            "risk": "low", "error": "", "outcome": "", "extra_steps": 0}


class R47DefaultWindowSpanTests(unittest.TestCase):
    """A long history must be described by its trailing window."""

    def test_degeneration_living_only_in_the_tail_reports_3_not_6(self):
        hist = [step(i, conf="strong" if i < 3 else "shaky") for i in range(6)]
        facts = mindseam.observations(hist)
        for fact in facts:
            if "seam" in fact:
                self.assertNotIn("6 seams", fact)
                self.assertNotIn("6 consecutive seams", fact)
        self.assertIn(
            "Every confidence tag in the last %d seams has been 'shaky'." % mindseam.STALL_RUN,
            facts)
        self.assertIn(
            "Marker 'OPEN' co-occurs with 'shaky' confidence across %d seams." % mindseam.STALL_RUN,
            facts)
        self.assertIn(
            "The same verifier has been used with 'shaky' confidence for %d consecutive seams."
            % mindseam.STALL_RUN,
            facts)


class R47CustomWindowSpanTests(unittest.TestCase):
    """A custom run= window must be reported, not the STALL_RUN constant."""

    def test_detect_stall_reports_the_custom_window(self):
        hist = [step(i, conf="shaky") for i in range(5)]
        self.assertEqual(
            mindseam.detect_stall(hist, run=hist[-2:]),
            ["Next action has not changed for 2 seams."])

    def test_observations_reports_the_custom_window(self):
        hist = [step(i, conf="shaky") for i in range(5)]
        facts = mindseam.observations(hist, run=hist[-2:])
        spanned = [f for f in facts if "seams" in f]
        self.assertTrue(spanned)
        for fact in spanned:
            self.assertIn("2 seams", fact)
            self.assertNotIn("5 seams", fact)

    def test_detect_volatility_reports_the_custom_window(self):
        hist = [step(i, conf=("strong", "thin")[i % 2]) for i in range(5)]
        self.assertEqual(
            mindseam.detect_volatility(hist, run=hist[-4:]),
            ["Confidence oscillated 3 times across the last 4 seams."])

    def test_mixed_window_oscillation_reports_the_window_not_the_history(self):
        hist = [step(0, conf="shaky"), step(1, conf="shaky"), step(2, conf="shaky"),
                step(3, conf="strong"), step(4, conf="shaky")]
        facts = mindseam.observations(hist, run=hist[-3:])
        self.assertIn(
            "Confidence oscillated 2 times across the last 3 seams.",
            facts)
        for fact in facts:
            self.assertNotIn("5 seams", fact)


if __name__ == "__main__":
    unittest.main()
