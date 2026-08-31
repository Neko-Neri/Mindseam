# -*- coding: utf-8 -*-
"""Round 55 guards: the short ledger shows two live core entries.

The hub doctrine is "two live at a time": the short seam view prints
the first two Core rows and summarises the rest as a count, the full
resume view prints every row, and both view modes agree on the
placeholders for empty sections. The guards pin the display contract
so a formatting change cannot silently bury hub entries.
"""

import contextlib
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam

BOOK = {"Goal": ["g"], "Next": ["dom: next"],
        "Core": ["one — fact", "two — fact", "three — fact",
                 "four — fact"],
        "Verified": ["✓01 a — verified by: x",
                     "✓02 b — verified by: y"],
        "Open": ["?01 q — settled by: t"]}


def render(fn, book):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        fn(book)
    return out.getvalue()


class LedgerDisplayTests(unittest.TestCase):

    def test_short_view_shows_two_live_and_counts_the_rest(self):
        out = render(mindseam.print_ledger, dict(BOOK))
        self.assertIn("one — fact", out)
        self.assertIn("two — fact", out)
        self.assertNotIn("three — fact", out)
        self.assertIn("(+2 more in the ledger — two live at a time)", out)

    def test_full_view_shows_every_row(self):
        out = render(mindseam.print_full_ledger, dict(BOOK))
        for row in BOOK["Core"]:
            self.assertIn(row, out)

    def test_full_view_marks_live_and_parked(self):
        out = render(mindseam.print_full_ledger, dict(BOOK))
        self.assertIn("[live] one — fact", out)
        self.assertIn("[parked] three — fact", out)

    def test_short_view_shows_last_verified_and_counts(self):
        out = render(mindseam.print_ledger, dict(BOOK))
        self.assertIn("✓02 b — verified by: y", out)
        self.assertIn("(1 earlier, in the ledger)", out)

    def test_empty_sections_have_placeholders(self):
        empty = {"Goal": [], "Next": [], "Core": [], "Verified": [],
                 "Open": []}
        out = render(mindseam.print_ledger, empty)
        self.assertIn("(not set)", out)
        self.assertIn("(empty)", out)
        self.assertIn("(none yet)", out)


if __name__ == "__main__":
    unittest.main()
