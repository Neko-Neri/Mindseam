# -*- coding: utf-8 -*-
"""Round 15 guards: degrade detection in assess_risk.

assess_risk flagged a degrading confidence trend only when the last three
labels matched the exact sequence strong, thin, shaky. A two-level
collapse (strong -> shaky) — strictly more alarming than the graded
trend — left the risk level at low, as did trends the exact triple
happened not to spell out letter for letter. The detector now reads the
ordered confidence levels: a sustained trend is every recent step worse
than the previous one, and a single-step two-level collapse is its own
high-risk reason. Everything else (marker repeat, stuck confidence,
missing metadata, missing next actions) keeps its original branch and
threshold.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def rows(*confidences):
    return [{"t": 1000 + i, "next": "dom: act %d" % i, "verified": 0,
             "open": 0, "marker": "", "confidence": c, "verifier": "",
             "risk": "", "error": "", "outcome": "", "extra_steps": 0}
            for i, c in enumerate(confidences)]


class DegradeDetectionTests(unittest.TestCase):

    def test_graded_trend_still_rates_high(self):
        level, reasons = mindseam.assess_risk(rows("strong", "thin", "shaky"))
        self.assertEqual(level, "high")
        self.assertIn("confidence trend is degrading", reasons)

    def test_two_level_collapse_rates_high(self):
        level, reasons = mindseam.assess_risk(
            rows("strong", "strong", "shaky"))
        self.assertEqual(level, "high")
        self.assertTrue(any("collapsed" in r for r in reasons), reasons)

    def test_short_history_collapse_rates_high(self):
        level, reasons = mindseam.assess_risk(rows("strong", "shaky"))
        self.assertEqual(level, "high")
        self.assertTrue(any("collapsed" in r for r in reasons), reasons)

    def test_mild_single_drop_stays_unflagged(self):
        # One strong -> thin step was never a risk trigger and still
        # is not; the graded trend needs every step worse.
        level, _ = mindseam.assess_risk(rows("strong", "strong", "thin"))
        self.assertEqual(level, "low")

    def test_partial_trend_falls_through_to_stuck(self):
        # strong -> thin -> thin is not a sustained trend; the stuck
        # branch catches the repeated thin instead.
        level, reasons = mindseam.assess_risk(rows("strong", "thin", "thin"))
        self.assertEqual(level, "medium")
        self.assertIn("confidence is stuck", reasons)

    def test_unknown_labels_never_crash_or_misfire(self):
        level, _ = mindseam.assess_risk(rows("strong", "confident", "shaky"))
        self.assertIn(level, ("low", "medium", "high"))


class OtherBranchesUnchangedTests(unittest.TestCase):

    def test_repeated_marker_keeps_medium(self):
        h = [{"t": 1000 + i, "next": "dom: x", "verified": 0, "open": 0,
              "marker": "OPEN", "confidence": "", "verifier": "", "risk": "",
              "error": "", "outcome": "", "extra_steps": 0}
             for i in range(3)]
        level, reasons = mindseam.assess_risk(h)
        self.assertEqual(level, "medium")
        self.assertIn("same marker repeated", reasons)

    def test_metadata_free_window_keeps_medium(self):
        h = [{"t": 1000 + i, "next": "dom: x", "verified": 0, "open": 0,
              "marker": "", "confidence": "", "verifier": "", "risk": "",
              "error": "", "outcome": "", "extra_steps": 0}
             for i in range(3)]
        level, reasons = mindseam.assess_risk(h)
        self.assertEqual(level, "medium")
        self.assertIn("recent entries have no confidence or marker", reasons)

    def test_missing_next_actions_keeps_high(self):
        h = [{"t": 1000 + i, "next": "", "verified": 0, "open": 0,
              "marker": "OPEN", "confidence": "strong", "verifier": "",
              "risk": "", "error": "", "outcome": "", "extra_steps": 0}
             for i in range(3)]
        level, reasons = mindseam.assess_risk(h)
        self.assertEqual(level, "high")
        self.assertIn("recent entries have no next actions", reasons)

    def test_clean_history_stays_low(self):
        h = [{"t": 1000 + i, "next": "dom: x %d" % i, "verified": i + 1,
              "open": 0, "marker": ["OPEN", "STEP", "DONE"][i],
              "confidence": "strong",
              "verifier": "v", "risk": "", "error": "", "outcome": "ok",
              "extra_steps": 0}
             for i in range(3)]
        level, reasons = mindseam.assess_risk(h)
        self.assertEqual(level, "low")
        self.assertEqual(reasons, [])


if __name__ == "__main__":
    unittest.main()
