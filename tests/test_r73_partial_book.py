# -*- coding: utf-8 -*-
"""Round 33 guards: a partial ledger is a measurement problem, not a crash.

one() indexed book[key] directly, so any scoring helper handed a ledger
mapping that lacked one of the five sections — a partial dict from a
caller, a stripped fixture, a future section rename — crashed with
KeyError instead of reading that section as empty. read_ledger always
returns all sections, but the scoring helpers are public and their book
parameter is unvalidated. one() now treats a missing section as no rows.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam

HIST = [{"t": 1000 + i, "next": "dom: step %d" % i, "verified": i + 1,
         "open": 0, "marker": "OPEN", "confidence": "strong",
         "verifier": "v", "risk": "low", "error": "", "outcome": "ok",
         "extra_steps": 0} for i in range(6)]

PARTIAL_BOOKS = [
    {},
    {"Goal": ["g"]},
    {"Next": ["dom: step"]},
    {"Goal": ["g"], "Next": ["dom: step"]},
    {"Core": ["c — fact"], "Open": ["?01 q — settled by: t"]},
]


class PartialBookTests(unittest.TestCase):

    def test_one_reads_missing_section_as_empty(self):
        self.assertEqual(mindseam.one({}, "Next"), "")
        self.assertEqual(mindseam.one({"Next": []}, "Next"), "")
        self.assertEqual(mindseam.one({"Next": ["x"]}, "Next"), "x")

    def test_ledger_aware_detectors_survive_partial_books(self):
        for book in PARTIAL_BOOKS:
            mindseam.ledger_stasis_detector(HIST, book)
            mindseam.goal_alignment_score(HIST, book=book)
            mindseam.stale_core_count(book)
            mindseam.detect_ledger_stagnation(HIST, book)

    def test_health_score_survives_partial_books(self):
        for book in PARTIAL_BOOKS:
            result = mindseam.session_health_score(HIST, book=book)
            self.assertIsInstance(result.score, int)

    def test_complete_book_behaviour_is_unchanged(self):
        full = {"Goal": ["g"], "Core": [], "Verified": [], "Open": [],
                "Next": ["dom: step 5"]}
        score, reasons = mindseam.session_health_score(HIST, book=full)
        self.assertTrue(
            any("ledger plan" in r for r in reasons), reasons)


if __name__ == "__main__":
    unittest.main()
