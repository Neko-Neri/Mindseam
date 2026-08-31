# -*- coding: utf-8 -*-
"""Round 57 guards: momentum and acceleration decision tables.

session_momentum compares the first and last cumulative verified counts
and feeds a ±5 fusion factor plus a resume fact; trend_acceleration
compares the rate of change across the two halves and feeds another ±5.
Both need STALL_RUN entries before they will say anything. The tables
pin the three-way decisions and the short-window silence.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def hist(verifieds):
    return [{"t": 1000 + i, "next": "dom: act %d" % i, "verified": v,
             "open": 0, "marker": "OPEN", "confidence": "strong",
             "verifier": "v", "risk": "low", "error": "",
             "outcome": "ok", "extra_steps": 0}
            for i, v in enumerate(verifieds)]


class MomentumTableTests(unittest.TestCase):

    def test_rising_is_positive(self):
        self.assertEqual(mindseam.session_momentum(hist([1, 2, 3])),
                         "positive")

    def test_falling_is_negative(self):
        self.assertEqual(mindseam.session_momentum(hist([3, 2, 1])),
                         "negative")

    def test_flat_is_stable(self):
        self.assertEqual(mindseam.session_momentum(hist([2, 2, 2])),
                         "stable")

    def test_short_history_is_stable(self):
        self.assertEqual(mindseam.session_momentum(hist([1, 5])), "stable")

    def test_velocity_is_capped_at_one(self):
        self.assertEqual(mindseam.momentum_velocity(hist([0, 0, 50])), 1.0)
        self.assertAlmostEqual(
            mindseam.momentum_velocity(hist([0, 0, 5])), 0.5)


class AccelerationTableTests(unittest.TestCase):

    def test_accelerating(self):
        self.assertEqual(
            mindseam.trend_acceleration(hist([1, 1, 1, 2, 3, 4])),
            "accelerating")

    def test_decelerating(self):
        self.assertEqual(
            mindseam.trend_acceleration(hist([1, 2, 3, 4, 4, 4])),
            "decelerating")

    def test_steady_growth_is_stable(self):
        self.assertEqual(
            mindseam.trend_acceleration(hist([1, 2, 3, 4, 5, 6])),
            "stable")

    def test_short_history_is_stable(self):
        self.assertEqual(mindseam.trend_acceleration(hist([1, 2])), "stable")

    def test_flat_verified_never_accelerates(self):
        self.assertEqual(
            mindseam.trend_acceleration(hist([3, 3, 3, 3, 3, 3])),
            "stable")


if __name__ == "__main__":
    unittest.main()
