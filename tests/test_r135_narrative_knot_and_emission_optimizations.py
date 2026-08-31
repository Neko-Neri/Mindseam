# -*- coding: utf-8 -*-
"""Round 63 guards: narrative knot detection and complexity emission optimizations.

complexity_emission_ratio, narrative_knot_detector, confidence_inflation,
and verification_temporal_bias previously used multi-pass list loops and
verbose accumulator variables. The detectors now use generator expressions
and set comprehensions, reducing memory footprint and eliminating redundant
branching while strictly preserving score formulas and invariants.
This round pins narrative retread detection, emission ratio edge cases, and
temporal verification symmetry.
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


class NarrativeKnotAndEmissionOptimizationsTests(unittest.TestCase):

    def test_complexity_emission_ratio_lean_and_delivered(self):
        # 0 extra steps with verified outcomes = 100
        hist = [
            {"extra_steps": 0, "verified": 1, "outcome": "ok"}
            for _ in range(mindseam.STALL_RUN)
        ]
        self.assertEqual(mindseam.complexity_emission_ratio(hist), 100)

        # Extra steps without deliverables = 0
        hist_stuck = [
            {"extra_steps": 2, "verified": 0, "outcome": ""}
            for _ in range(mindseam.STALL_RUN)
        ]
        self.assertEqual(mindseam.complexity_emission_ratio(hist_stuck), 0)

    def test_narrative_knot_detector_retread(self):
        # 6 steps: prior 3 explore alpha, beta, gamma; recent 3 retread alpha
        hist = [
            {"next": "alpha:step1"},
            {"next": "beta:step2"},
            {"next": "gamma:step3"},
            {"next": "alpha:step1"},
            {"next": "alpha:step1"},
            {"next": "alpha:step1"},
        ]
        score = mindseam.narrative_knot_detector(hist)
        # All 3 recent steps retread prior -> score = 0
        self.assertEqual(score, 0)

    def test_verification_temporal_bias_symmetric_vs_biased(self):
        # 6 steps: symmetric verification across both halves
        hist_sym = [
            {"verified": 1}, {"verified": 1}, {"verified": 1},
            {"verified": 1}, {"verified": 1}, {"verified": 1},
        ]
        self.assertEqual(mindseam.verification_temporal_bias(hist_sym), 100)

        # Verification clustered entirely in second half
        hist_biased = [
            {"verified": 0}, {"verified": 0}, {"verified": 0},
            {"verified": 1}, {"verified": 1}, {"verified": 1},
        ]
        self.assertLess(mindseam.verification_temporal_bias(hist_biased), 50)


if __name__ == "__main__":
    unittest.main()
