# -*- coding: utf-8 -*-
"""Round 49 guards: clean_scalar is the one-line gate for every flag.

Every scalar the CLI accepts passes through clean_scalar. The matrix
pins its contract: None passes through (flag absent), surrounding
whitespace is trimmed, blank-after-trim is refused, embedded newlines
and carriage returns are refused (the ledger is line-oriented), and a
genuine one-line value survives byte-for-byte.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


class CleanScalarTests(unittest.TestCase):

    def test_none_passes_through(self):
        self.assertEqual(mindseam.clean_scalar(None), (None, None))

    def test_surrounding_whitespace_is_trimmed(self):
        self.assertEqual(mindseam.clean_scalar("  ship it  "),
                         ("ship it", None))

    def test_blank_after_trim_is_refused(self):
        value, problem = mindseam.clean_scalar("   ")
        self.assertIsNone(value)
        self.assertIn("empty", problem)

    def test_embedded_newline_is_refused(self):
        value, problem = mindseam.clean_scalar("two\nlines")
        self.assertIsNone(value)
        self.assertIn("one line", problem)

    def test_carriage_return_is_refused(self):
        value, problem = mindseam.clean_scalar("two\r\nlines")
        self.assertIsNone(value)
        self.assertIn("one line", problem)

    def test_lone_carriage_return_is_refused(self):
        value, problem = mindseam.clean_scalar("a\rb")
        self.assertIsNone(value)
        self.assertIn("one line", problem)

    def test_real_value_survives(self):
        self.assertEqual(
            mindseam.clean_scalar("dom: act — including edge cases"),
            ("dom: act — including edge cases", None))

    def test_heading_prefix_is_caught_by_the_caller(self):
        # The '## ' guard lives in mode_note for goal/next only; the
        # scalar gate itself stays content-neutral.
        value, problem = mindseam.clean_scalar("## Heading")
        self.assertEqual(value, "## Heading")
        self.assertIsNone(problem)


if __name__ == "__main__":
    unittest.main()
