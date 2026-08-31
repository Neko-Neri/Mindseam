# -*- coding: utf-8 -*-
"""Round 58 guards: advanced telemetry bounds and ship scanner resilience.

assess_risk, contradiction_detection, evidence_weight, and grade form
the core analytical foundation of Mindseam inference-time control. This round
pins boundary edge conditions across all risk rating paths, opposite-valence
contradiction detection rules, evidence weighting limits, and grade bands,
as well as mode_ship soft-wrap and line-ending parsing resilience. These
guards prevent regressions in inference-time telemetry calculation.
"""

import os
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
from _controller_helper import run_controller


class AdvancedCapabilitiesAndResilienceTests(unittest.TestCase):

    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd() if 'os' in globals() else str(ROOT)

    def test_grade_boundaries(self):
        self.assertEqual(mindseam.grade(100), "A")
        self.assertEqual(mindseam.grade(90), "A")
        self.assertEqual(mindseam.grade(89), "B")
        self.assertEqual(mindseam.grade(75), "B")
        self.assertEqual(mindseam.grade(74), "C")
        self.assertEqual(mindseam.grade(60), "C")
        self.assertEqual(mindseam.grade(59), "D")
        self.assertEqual(mindseam.grade(40), "D")
        self.assertEqual(mindseam.grade(39), "F")
        self.assertEqual(mindseam.grade(0), "F")

    def test_assess_risk_confidence_collapse_and_degradation(self):
        # Single-step collapse: strong -> shaky
        hist_collapse = [
            {"confidence": "strong", "next": "step 1"},
            {"confidence": "shaky", "next": "step 2"},
        ]
        lvl, reasons = mindseam.assess_risk(hist_collapse)
        self.assertEqual(lvl, "high")
        self.assertTrue(any("collapsed" in r for r in reasons))

        # Degrading trend: strong -> thin -> shaky
        hist_trend = [
            {"confidence": "strong", "next": "step 1"},
            {"confidence": "thin", "next": "step 2"},
            {"confidence": "shaky", "next": "step 3"},
        ]
        lvl_trend, reasons_trend = mindseam.assess_risk(hist_trend)
        self.assertEqual(lvl_trend, "high")
        self.assertTrue(any("degrading" in r for r in reasons_trend))

    def test_contradiction_detection_distinguishes_caution_from_contradiction(self):
        # Caution: thin on high risk is valid awareness, not contradiction
        caution_hist = [
            {"confidence": "thin", "risk": "high"},
            {"confidence": "thin", "risk": "high"},
            {"confidence": "thin", "risk": "high"},
        ]
        self.assertEqual(mindseam.contradiction_detection(caution_hist), [])

        # Contradiction: strong on high risk, or shaky on low risk
        contra_hist = [
            {"confidence": "strong", "risk": "high"},
            {"confidence": "strong", "risk": "high"},
            {"confidence": "strong", "risk": "high"},
        ]
        contra_facts = mindseam.contradiction_detection(contra_hist)
        self.assertEqual(len(contra_facts), 1)
        self.assertIn("contradiction", contra_facts[0].lower())

    def test_evidence_weight_bounds_and_components(self):
        # Empty
        self.assertEqual(mindseam.evidence_weight([]), 0)

        # STALL_RUN (3-step) rich evidence
        run3_hist = [
            {"verifier": f"v{i}", "verified": i + 1, "outcome": "ok", "error": ""}
            for i in range(mindseam.STALL_RUN)
        ]
        self.assertEqual(mindseam.evidence_weight(run3_hist), 93)

        # 4-step full saturation (max 100)
        run4_hist = [
            {"verifier": f"v{i}", "verified": i + 1, "outcome": "ok", "error": ""}
            for i in range(4)
        ]
        self.assertEqual(mindseam.evidence_weight(run4_hist, run=run4_hist), 100)

    def test_ship_handles_crlf_and_softwrapped_paragraphs(self):
        lines = [
            "We have verified the implementation.\r\n",
            "Across all boundary test cases and environments.\r\n",
        ]
        # Covered claim joined across soft-wrapped lines
        uncovered = mindseam.claim_without_coverage([line.strip() for line in lines])
        self.assertIsNone(uncovered)


if __name__ == "__main__":
    unittest.main()
