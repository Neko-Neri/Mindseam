# -*- coding: utf-8 -*-
"""Round 76 guards: trend_acceleration direct boundary slicing and epistemic drift detection.

trend_acceleration compares velocity gradients across adjacent time windows to detect
acceleration or deceleration in verified progress. The detector previously used manual
element-by-element loops with multiple None-checks and counter variables. It has been
refactored with direct O(1) slice boundary indexing (first_slice[0], first_slice[-1]),
eliminating loop overhead while maintaining exact floating-point gradient comparisons.
This round pins acceleration detection, deceleration detection, and stable cadence contracts.
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


class TrendAccelerationSlicingTests(unittest.TestCase):

    def _make_hist(self, verified_counts):
        return [{"verified": v, "open": 0, "next": f"step_{i}"} for i, v in enumerate(verified_counts)]

    def test_trend_acceleration_accelerating(self):
        # Window 1: [1, 1, 1] (rate = 0.0), Window 2: [2, 3, 5] (rate = 1.0) -> accelerating
        hist = self._make_hist([1, 1, 1, 2, 3, 5])
        self.assertEqual(mindseam.trend_acceleration(hist), "accelerating")

    def test_trend_acceleration_decelerating(self):
        # Window 1: [1, 3, 5] (rate = 1.33), Window 2: [5, 5, 5] (rate = 0.0) -> decelerating
        hist = self._make_hist([1, 3, 5, 5, 5, 5])
        self.assertEqual(mindseam.trend_acceleration(hist), "decelerating")

    def test_trend_acceleration_steady_is_stable(self):
        # Window 1: [1, 2, 3] (rate = 0.66), Window 2: [4, 5, 6] (rate = 0.66) -> stable
        hist = self._make_hist([1, 2, 3, 4, 5, 6])
        self.assertEqual(mindseam.trend_acceleration(hist), "stable")

    def test_trend_acceleration_below_minimum_span_is_stable(self):
        # Fewer than STALL_RUN * 2 entries
        hist = self._make_hist([1, 2, 3, 4])
        self.assertEqual(mindseam.trend_acceleration(hist), "stable")


if __name__ == "__main__":
    unittest.main()
