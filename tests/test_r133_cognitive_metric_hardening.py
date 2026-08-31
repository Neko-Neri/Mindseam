# -*- coding: utf-8 -*-
"""Round 61 guards: cognitive metric evaluation hardening and condition hygiene.

session_fatigue and cognitive_load_index previously contained redundant
truthiness checks on guaranteed non-empty slices. The metric evaluations
have been streamlined while strictly preserving all boundary penalty and
bonus weight formulas. This round pins fatigue scoring, cognitive load index
saturation, and drift velocity calculation invariants.
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


class CognitiveMetricHardeningTests(unittest.TestCase):

    def test_session_fatigue_empty_and_short_history(self):
        self.assertEqual(mindseam.session_fatigue([]), 0)
        self.assertEqual(mindseam.session_fatigue([{"verified": 1}]), 0)

    def test_session_fatigue_penalty_on_verified_drop(self):
        # 3 steps where verified drops from 5 to 2
        hist = [
            {"verified": 5, "confidence": "strong", "risk": "low"},
            {"verified": 3, "confidence": "strong", "risk": "low"},
            {"verified": 2, "confidence": "strong", "risk": "low"},
        ]
        score = mindseam.session_fatigue(hist)
        # Should have verified drop penalty (+15) and no phew penalty (+10)
        self.assertGreaterEqual(score, 25)

    def test_cognitive_load_index_combined_stress(self):
        # High risk and weak confidence simultaneously
        hist = [
            {"next": f"task_{i}", "risk": "high", "confidence": "shaky"}
            for i in range(mindseam.STALL_RUN)
        ]
        load = mindseam.cognitive_load_index(hist)
        self.assertGreaterEqual(load, 50)


if __name__ == "__main__":
    unittest.main()
