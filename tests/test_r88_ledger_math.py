# -*- coding: utf-8 -*-
"""Round 50 guards: ledger ratio and completeness boundary math.

coverage_ratio drives the "70%+ open" fact and a remediation line;
completeness_score drives the "completeness is low" branch and the
ledger remediation. Their boundary arithmetic is pinned: empty ledger,
zero denominators, the 0.7 coverage edge, and the >10-open penalty
slope (two points per extra open item, floored at zero).
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def book(core=0, verified=0, opened=0):
    return {"Goal": ["g"], "Next": ["n"],
            "Core": ["c%d — f" % i for i in range(core)],
            "Verified": ["✓%02d x — verified by: y" % i
                         for i in range(verified)],
            "Open": ["?%02d q — settled by: t" % i
                     for i in range(opened)]}


class CoverageRatioTests(unittest.TestCase):

    def test_empty_ledger_has_zero_coverage(self):
        self.assertEqual(mindseam.coverage_ratio(book(0, 0, 0)), 0.0)

    def test_half_open_is_reported(self):
        self.assertAlmostEqual(
            mindseam.coverage_ratio(book(1, 1, 2)), 0.5)

    def test_the_seventy_percent_edge(self):
        # 7 open out of 10 rows is exactly the fact threshold.
        self.assertAlmostEqual(
            mindseam.coverage_ratio(book(1, 2, 7)), 0.7)


class CompletenessScoreTests(unittest.TestCase):

    def test_empty_ledger_scores_zero(self):
        self.assertEqual(mindseam.completeness_score(book(0, 0, 0)), 0)

    def test_all_verified_scores_hundred(self):
        self.assertEqual(mindseam.completeness_score(book(0, 4, 0)), 100)

    def test_open_flood_is_penalised_two_points_per_extra(self):
        # Exact pin: 10 verified of 21 rows is 47 base, and the 11th
        # open item costs its two points on top.
        self.assertEqual(mindseam.completeness_score(book(0, 10, 10)), 50)
        self.assertEqual(mindseam.completeness_score(book(0, 10, 11)), 45)

    def test_penalty_floors_at_zero(self):
        self.assertEqual(mindseam.completeness_score(book(0, 1, 60)), 0)

    def test_score_never_exceeds_hundred(self):
        self.assertEqual(mindseam.completeness_score(book(0, 9, 0)), 100)


if __name__ == "__main__":
    unittest.main()
