# -*- coding: utf-8 -*-
"""Round 80 guards: learning_rate generator optimization and adaptability comprehensions.

learning_rate measures the rate of learnable evidence signals (verified steps, outcomes,
or logged errors) produced per step across the evaluation window. adaptability_score
evaluates whether an agent pivots after encountering stalls or rising risks. Both functions
have been refactored with clean set/list comprehensions and generator expression sums,
streamlining evaluation while preserving exact floating point ratios and adaptability scores.
This round pins 100% learning rate, zero evidence baseline, and stall breakout adjustments.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import mindseam


class LearningRateAndAdaptabilityTests(unittest.TestCase):

    def test_learning_rate_zero_evidence(self):
        hist = [
            {"verified": 0, "outcome": "", "error": "", "next": "s1"},
            {"verified": 0, "outcome": "", "error": "", "next": "s2"},
            {"verified": 0, "outcome": "", "error": "", "next": "s3"},
        ]
        self.assertAlmostEqual(mindseam.learning_rate(hist), 0.0)

    def test_learning_rate_full_evidence_output(self):
        hist = [
            {"verified": 1, "outcome": "", "error": "", "next": "s1"},
            {"verified": 0, "outcome": "ok", "error": "", "next": "s2"},
            {"verified": 0, "outcome": "", "error": "timeout", "next": "s3"},
        ]
        self.assertAlmostEqual(mindseam.learning_rate(hist), 1.0)

    def test_adaptability_score_stall_breakout_and_growth(self):
        # 3 stalled entries followed by a breakout action, with multiple verified values
        hist = [
            {"verified": 1, "risk": "low", "next": "stalled"},
            {"verified": 1, "risk": "low", "next": "stalled"},
            {"verified": 1, "risk": "low", "next": "stalled"},
            {"verified": 2, "risk": "low", "next": "pivoted action"},
        ]
        score = mindseam.adaptability_score(hist)
        # 35 (stall breakout) + 25 (multiple verified values) = 60
        self.assertEqual(score, 60)


if __name__ == "__main__":
    unittest.main()
