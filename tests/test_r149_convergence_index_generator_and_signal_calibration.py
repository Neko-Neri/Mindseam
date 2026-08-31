# -*- coding: utf-8 -*-
"""Round 77 guards: convergence_index generator optimization and signal calibration.

convergence_index measures agreement across multi-dimensional cognitive signals (risk,
confidence, momentum, volatility). The counting logic previously iterated over signals
using manual accumulator variables with continue statements. It has been refactored
with clean generator sum expressions (sum(1 for s in signals if s > 0)), streamlining
signal aggregation while preserving exact 0-100 index calibration. This round pins
unanimous positive convergence, unanimous negative convergence, and conflict divergence.
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


class ConvergenceIndexGeneratorTests(unittest.TestCase):

    def test_convergence_index_empty_history_defaults_50(self):
        self.assertEqual(mindseam.convergence_index([]), 50)

    def test_convergence_index_unanimous_positive(self):
        # low risk (1), strong confidence (1), positive momentum (1), zero volatility (1)
        hist = [
            {"verified": 1, "risk": "low", "confidence": "strong", "next": "s1"},
            {"verified": 2, "risk": "low", "confidence": "strong", "next": "s2"},
            {"verified": 3, "risk": "low", "confidence": "strong", "next": "s3"},
        ]
        conv = mindseam.convergence_index(hist)
        self.assertEqual(conv, 100)

    def test_convergence_index_unanimous_negative(self):
        # high risk (-1), shaky confidence (-1), negative momentum (-1), high volatility (-1)
        hist = [
            {"verified": 3, "risk": "high", "confidence": "strong", "next": "s1"},
            {"verified": 2, "risk": "high", "confidence": "shaky", "next": "s2"},
            {"verified": 1, "risk": "high", "confidence": "thin", "next": "s3"},
        ]
        conv = mindseam.convergence_index(hist)
        self.assertEqual(conv, 0)

    def test_convergence_index_conflicting_signals(self):
        # conflicting: high risk (-1) with strong confidence (1)
        hist = [
            {"verified": 1, "risk": "high", "confidence": "strong", "next": "s1"},
            {"verified": 2, "risk": "high", "confidence": "strong", "next": "s2"},
            {"verified": 3, "risk": "high", "confidence": "strong", "next": "s3"},
        ]
        conv = mindseam.convergence_index(hist)
        self.assertLess(conv, 50)


if __name__ == "__main__":
    unittest.main()
