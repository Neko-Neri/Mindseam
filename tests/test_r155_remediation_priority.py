# -*- coding: utf-8 -*-
"""Round 155 guards: remediation suggestions sort by severity, not fact order.

``remediation_suggestions`` previously preserved the order in which
observations surfaced their facts, so a fact list of
``[oscillated, escalated, degradation]`` ranked a transient signal above
a worsening one purely because it was observed later. The map now
records a priority for every entry, and the list is sorted by that
priority before the cap is applied. The critically-stressed line is
hoisted to index 0 whenever the score is below 30, exactly as before.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def _find(text, suggestions):
    for index, item in enumerate(suggestions):
        if text in item:
            return index
    return -1


class RemediationPriorityTests(unittest.TestCase):

    def test_priority_ranks_degradation_above_oscillation(self):
        # A fact list of three items in the wrong severity order: the
        # "oscillated" line has priority 6, "escalated" 2, "degradation" 0.
        # The published output must rank degradation first, even though
        # it was the third fact emitted.
        facts = [
            "Confidence oscillated 2 times across the last 3 seams.",
            "Risk escalated across recent seams: low -> high.",
            "Confidence trend shows degradation: strong -> shaky.",
        ]
        out = mindseam.remediation_suggestions(facts, 80)
        self.assertNotEqual(out, [],
                            "degradation / escalation / oscillation must all match")
        rank_deg = _find("Confidence is degrading", out)
        rank_esc = _find("Risk is climbing", out)
        rank_osc = _find("Confidence keeps shifting", out)
        self.assertGreaterEqual(rank_deg, 0)
        self.assertGreaterEqual(rank_esc, 0)
        self.assertGreaterEqual(rank_osc, 0)
        self.assertLess(rank_deg, rank_esc)
        self.assertLess(rank_esc, rank_osc)

    def test_priority_ranks_recovery_last(self):
        facts = [
            "Risk recovered across recent seams: high -> low.",
            "Risk escalated across recent seams: low -> high.",
        ]
        out = mindseam.remediation_suggestions(facts, 80)
        rank_rec = _find("Risk has improved", out)
        rank_esc = _find("Risk is climbing", out)
        self.assertGreater(rank_rec, rank_esc,
                           "recovery must trail escalation; got %r" % out)

    def test_priority_cap_at_six_still_holds(self):
        facts = [
            "Confidence trend shows degradation: strong -> shaky.",
            "Stall severity is high (70/100); session has lost momentum.",
            "Risk escalated across recent seams: low -> high.",
            "Verified outcomes are inaccessible (3/3 entries).",
            "No new verification across the last 3 seams.",
            "Next action has not changed for 3 seams.",
            "Confidence oscillated 2 times across the last 3 seams.",
            "2 core item(s) have gone unverified across 8 seams.",
        ]
        out = mindseam.remediation_suggestions(facts, 80)
        self.assertEqual(len(out), 6, out)
        # Top of the list is the highest-severity key, which is "degradation".
        self.assertIn("Confidence is degrading", out[0], out)

    def test_critical_stress_hoist_remains_at_index_zero(self):
        facts = [
            "Confidence trend shows degradation: strong -> shaky.",
            "Risk escalated across recent seams: low -> high.",
        ]
        out = mindseam.remediation_suggestions(facts, 20)
        self.assertTrue(out[0].startswith("Session is critically stressed"),
                        out)
        # Degradation and escalation follow the hoist, in severity order.
        self.assertIn("Confidence is degrading", out[1])
        self.assertIn("Risk is climbing", out[2])

    def test_ledger_advice_uses_lower_priority_than_facts(self):
        # When the ledger is over 70% open and a fact already fires, the
        # ledger line should still be considered after the fact-keyed
        # advice in the output order.
        book = {
            "Goal": ["g"],
            "Core": ["c1", "c2"],
            "Verified": ["v1", "v2"],
            "Open": ["o"] * 10,
            "Next": ["n"],
        }
        # 10 open out of 14 total rows is roughly 71% coverage.
        facts = [
            "Confidence trend shows degradation: strong -> shaky.",
        ]
        out = mindseam.remediation_suggestions(facts, 80, book=book)
        rank_deg = _find("Confidence is degrading", out)
        rank_cov = _find("Ledger coverage is high", out)
        self.assertGreaterEqual(rank_deg, 0)
        self.assertGreaterEqual(rank_cov, 0)
        self.assertLess(rank_deg, rank_cov,
                        "fact-keyed advice must precede ledger advice; got %r"
                        % out)


if __name__ == "__main__":
    unittest.main()
