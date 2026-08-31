# -*- coding: utf-8 -*-
"""Round 72 guards: observations streamlining and cognitive scaffold boundary contracts.

observations() performs fact-only extraction over recent seam history, scanning for
verified outcome accessibility, monotonic open-question growth, repetitive markers,
and risk escalation signals. The evaluation loop was streamlined to unify verified
truthiness checks and eliminate redundant comparison overhead. This round pins
inaccessible verified outcome detection, monotonic open-question growth, and
cognitive scaffold observation contracts.
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


class ObservationsStreamliningAndScaffoldTests(unittest.TestCase):

    def test_observations_inaccessible_verified_outcomes(self):
        # 3 seams with verified > 0 but missing outcome records
        hist = [
            {"verified": 1, "open": 0, "next": "step 1", "outcome": ""},
            {"verified": 2, "open": 0, "next": "step 2", "outcome": ""},
            {"verified": 3, "open": 0, "next": "step 3", "outcome": ""},
        ]
        facts = mindseam.observations(hist)
        self.assertTrue(any("Verified outcomes are inaccessible" in f for f in facts))

    def test_observations_accessible_verified_outcomes(self):
        # 3 seams with verified > 0 and populated outcome records
        hist = [
            {"verified": 1, "open": 0, "next": "step 1", "outcome": "ok"},
            {"verified": 2, "open": 0, "next": "step 2", "outcome": "ok"},
            {"verified": 3, "open": 0, "next": "step 3", "outcome": "ok"},
        ]
        facts = mindseam.observations(hist)
        self.assertFalse(any("Verified outcomes are inaccessible" in f for f in facts))

    def test_observations_monotonic_open_growth(self):
        hist = [
            {"verified": 0, "open": 1, "next": "step 1"},
            {"verified": 0, "open": 2, "next": "step 2"},
            {"verified": 0, "open": 3, "next": "step 3"},
        ]
        facts = mindseam.observations(hist)
        self.assertTrue(any("Open-question count increased at every seam" in f for f in facts))


if __name__ == "__main__":
    unittest.main()
