# -*- coding: utf-8 -*-
"""Round 52 guards: the assess_risk decision table.

assess_risk labels every history row and drives the Telemetry risk
line, the persisted risk state, and half a dozen downstream detectors.
The table pins each branch with its published reason: graded degrade,
two-level collapse, repeated marker, stuck weak confidence, missing
metadata, missing next actions — and the clean row that must stay low.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def rows(*pairs):
    """pairs: (confidence, marker) tuples; next always present."""
    return [{"t": 1000 + i, "next": "dom: act %d" % i, "verified": 0,
             "open": 0, "marker": m, "confidence": c, "verifier": "",
             "risk": "", "error": "", "outcome": "", "extra_steps": 0}
            for i, (c, m) in enumerate(pairs)]


class RiskDecisionTableTests(unittest.TestCase):

    def test_graded_degrade_is_high(self):
        level, reasons = mindseam.assess_risk(
            rows(("strong", ""), ("thin", ""), ("shaky", "")))
        self.assertEqual(level, "high")
        self.assertIn("confidence trend is degrading", reasons)

    def test_collapse_is_high(self):
        level, reasons = mindseam.assess_risk(
            rows(("strong", ""), ("strong", ""), ("shaky", "")))
        self.assertEqual(level, "high")
        self.assertTrue(any("collapsed" in r for r in reasons))

    def test_repeated_marker_is_medium(self):
        level, reasons = mindseam.assess_risk(
            rows(("", "OPEN"), ("", "OPEN")))
        self.assertEqual(level, "medium")
        self.assertIn("same marker repeated", reasons)

    def test_stuck_thin_is_medium(self):
        level, reasons = mindseam.assess_risk(
            rows(("thin", ""), ("thin", ""), ("thin", "")))
        self.assertEqual(level, "medium")
        self.assertIn("confidence is stuck", reasons)

    def test_stuck_strong_is_not_medium(self):
        level, reasons = mindseam.assess_risk(
            rows(("strong", ""), ("strong", ""), ("strong", "")))
        self.assertEqual(level, "low")
        self.assertEqual(reasons, [])

    def test_metadata_free_window_is_medium(self):
        level, reasons = mindseam.assess_risk(rows(("", ""), ("", ""), ("", "")))
        self.assertEqual(level, "medium")
        self.assertIn("recent entries have no confidence or marker", reasons)

    def test_missing_next_actions_is_high(self):
        h = [{"t": 1000 + i, "next": "", "verified": 0, "open": 0,
              "marker": "OPEN", "confidence": "strong", "verifier": "",
              "risk": "", "error": "", "outcome": "", "extra_steps": 0}
             for i in range(3)]
        level, reasons = mindseam.assess_risk(h)
        self.assertEqual(level, "high")
        self.assertIn("recent entries have no next actions", reasons)

    def test_clean_row_stays_low(self):
        level, reasons = mindseam.assess_risk(
            rows(("strong", "OPEN"), ("strong", "DONE")))
        self.assertEqual(level, "low")
        self.assertEqual(reasons, [])


if __name__ == "__main__":
    unittest.main()
