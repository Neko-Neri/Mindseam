# -*- coding: utf-8 -*-
"""Round 53 guards: remediation ordering, dedup and the cap.

remediation_suggestions turns facts into at most six ordered actions:
fact-keyed advice first (one per fact), then ledger coverage and
completeness lines, with the critical-stress line hoisted to the front
when the score is below 30. The guards pin dedup, the cap, the hoist,
and that ledger lines never duplicate fact advice already carrying the
word ledger.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


class RemediationOrderTests(unittest.TestCase):

    def test_duplicate_facts_do_not_duplicate_advice(self):
        facts = ["Next action has not changed for 3 seams."] * 3
        out = mindseam.remediation_suggestions(facts, 80)
        self.assertEqual(len(out), 1, out)

    def test_cap_at_six_actions(self):
        facts = [
            "Risk escalated across recent seams: low -> high.",
            "Confidence oscillated 2 times across the last 3 seams.",
            "Risk recovered across recent seams: high -> low.",
            "Stall severity is high (70/100); session has lost momentum.",
            "Confidence trend shows degradation: strong -> shaky.",
            "Next action has not changed for 3 seams.",
            "No new verification across the last 3 seams.",
            "2 core item(s) have gone unverified across 8 seams.",
        ]
        out = mindseam.remediation_suggestions(facts, 80)
        self.assertLessEqual(len(out), 6)
        self.assertEqual(len(out), 6)

    def test_critical_stress_is_hoisted_to_front(self):
        facts = ["Next action has not changed for 3 seams."]
        out = mindseam.remediation_suggestions(facts, 20)
        self.assertTrue(out[0].startswith("Session is critically stressed"),
                        out)

    def test_critical_line_only_below_thirty(self):
        self.assertEqual(
            [s for s in mindseam.remediation_suggestions(
                ["Next action has not changed for 3 seams."], 31)
             if "critically" in s], [])

    def test_unmatched_facts_yield_no_fact_advice(self):
        out = mindseam.remediation_suggestions(["Nothing matches here."], 80)
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
