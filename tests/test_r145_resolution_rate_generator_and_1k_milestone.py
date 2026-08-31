# -*- coding: utf-8 -*-
"""Round 73 guards: resolution_rate generator optimization and 1,000+ tests milestone.

resolution_rate evaluates the fraction of recent seams in the evaluation window that
achieved closure via a recorded outcome or verified step. The accumulator loop has
been refactored with a clean generator expression sum, eliminating manual counter
increments while preserving exact floating point ratios. This round pins resolution
rate boundary calculations, mixed outcome/verification counting, and celebrates
crossing the 1,000 unit test milestone.
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


class ResolutionRateGeneratorTests(unittest.TestCase):

    def test_resolution_rate_with_all_resolved(self):
        hist = [
            {"verified": 1, "outcome": "ok", "next": "step 1"},
            {"verified": 2, "outcome": "ok", "next": "step 2"},
            {"verified": 3, "outcome": "ok", "next": "step 3"},
        ]
        rate = mindseam.resolution_rate(hist)
        self.assertAlmostEqual(rate, 1.0)

    def test_resolution_rate_with_zero_resolved(self):
        hist = [
            {"verified": 0, "outcome": "", "next": "step 1"},
            {"verified": 0, "outcome": "", "next": "step 2"},
            {"verified": 0, "outcome": "", "next": "step 3"},
        ]
        rate = mindseam.resolution_rate(hist)
        self.assertAlmostEqual(rate, 0.0)

    def test_resolution_rate_with_mixed_outcomes_and_verifications(self):
        hist = [
            {"verified": 1, "outcome": "", "next": "step 1"},  # resolved via verified
            {"verified": 0, "outcome": "failed: bad parse", "next": "step 2"},  # resolved via outcome
            {"verified": 0, "outcome": "", "next": "step 3"},  # unresolved
        ]
        rate = mindseam.resolution_rate(hist)
        self.assertAlmostEqual(rate, 2.0 / 3.0)


if __name__ == "__main__":
    unittest.main()
