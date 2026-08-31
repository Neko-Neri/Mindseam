# -*- coding: utf-8 -*-
"""Round 62 guards: adaptability slice evaluation and tension resolution math.

adaptability_score previously used a reversed list iteration with index
branches to compute earlier versus recent window risk sums. The evaluation
is now unified with direct negative slicing, strictly preserving risk descent
(+40), stall breakout (+35), and verification growth (+25) scoring weights.
This round pins adaptability slice parity, stall breakout detection, and
tension resolution easing formulas.
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import mindseam


class AdaptabilityAndTensionResolutionMathTests(unittest.TestCase):

    def test_adaptability_score_risk_descent(self):
        # 6 steps: first 3 high risk, last 3 low risk -> risk descent +40
        hist = [
            {"risk": "high", "verified": 0, "next": "step 0"},
            {"risk": "high", "verified": 0, "next": "step 1"},
            {"risk": "high", "verified": 0, "next": "step 2"},
            {"risk": "low", "verified": 0, "next": "step 3"},
            {"risk": "low", "verified": 0, "next": "step 4"},
            {"risk": "low", "verified": 0, "next": "step 5"},
        ]
        score = mindseam.adaptability_score(hist)
        self.assertEqual(score, 40)

    def test_adaptability_score_stall_breakout(self):
        # 3 identical nexts followed by a new action -> stall breakout +35
        hist = [
            {"risk": "low", "verified": 0, "next": "same action"},
            {"risk": "low", "verified": 0, "next": "same action"},
            {"risk": "low", "verified": 0, "next": "same action"},
            {"risk": "low", "verified": 0, "next": "different action"},
        ]
        score = mindseam.adaptability_score(hist)
        self.assertEqual(score, 35)

    def test_tension_resolution_with_phew_and_open_drop(self):
        # Open questions drop and PHEW recorded with verified progress
        hist = [
            {"open": 3, "marker": "OPEN", "risk": "low", "verified": 1, "next": "step 1"},
            {"open": 2, "marker": "OPEN", "risk": "low", "verified": 2, "next": "step 2"},
            {"open": 1, "marker": "PHEW", "risk": "low", "verified": 3, "next": "step 3"},
        ]
        score = mindseam.tension_resolution(hist)
        # open drop (+35), has_phew (+25), stall_free (+15) = 75
        self.assertEqual(score, 75)


if __name__ == "__main__":
    unittest.main()
