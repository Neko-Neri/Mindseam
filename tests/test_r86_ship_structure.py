# -*- coding: utf-8 -*-
"""Round 48 guards: structural Markdown never counts as prose leakage.

markdown_structural_lines exists so the register scan reads claims, not
layout: fenced blocks, headings, setext underlines and table rows are
carved out before INNER_ONLY and repetition scans run. The guards pin
the carve-outs that are easiest to regress — a setext heading pair, a
pipe table with its delimiter row, an unclosed fence swallowing the
rest of the file — and one leak that must still fire inside real prose.
"""

import io
import contextlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam

BOOK = {"Goal": ["g"], "Core": [], "Verified": [], "Open": [],
        "Next": ["n"]}


def ship(text):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        mindseam.mode_ship(dict(BOOK), text)
    return out.getvalue()


class StructuralCarveOutTests(unittest.TestCase):

    def test_setext_heading_is_structural(self):
        lines = ["A Claim About Results", "======================="]
        self.assertIn(0, mindseam.markdown_structural_lines(lines))
        self.assertIn(1, mindseam.markdown_structural_lines(lines))

    def test_table_rows_are_structural(self):
        lines = ["| case | result |", "|---|---|", "| empty | ok |"]
        structural = mindseam.markdown_structural_lines(lines)
        for index in range(3):
            self.assertIn(index, structural)

    def test_unclosed_fence_swallows_the_tail(self):
        text = "intro\n```\nverified => verified => verified\n"
        out = ship(text)
        self.assertNotIn("Found:", out)

    def test_prose_leak_still_fires_outside_structure(self):
        out = ship("plain prose with a ⇒ arrow in it")
        self.assertIn("Found:", out)

    def test_claim_in_table_does_not_trigger_coverage_gate(self):
        text = ("| statement | evidence |\n"
                "|---|---|\n"
                "| verified | none |\n")
        out = ship(text)
        self.assertNotIn("verification covered", out)


if __name__ == "__main__":
    unittest.main()
