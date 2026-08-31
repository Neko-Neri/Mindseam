# -*- coding: utf-8 -*-
"""Round 74 guards: every round file keeps its audit trail.

The suite's history lives in its file names and docstrings: each
test_rNN file opens with a docstring naming the round and the defect or
contract it pins, so a future maintainer can read the progression
without git archaeology. The guard pins the convention: no round file
without a substantive docstring, no number gaps in the sequence.
"""

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ROUND_FILES = sorted(ROOT.glob("tests/test_r[0-9][0-9][0-9]_*.py"))


class RoundHygieneTests(unittest.TestCase):

    def test_round_numbers_have_no_gaps(self):
        numbers = sorted(int(p.name.split("_")[1][1:])
                         for p in ROUND_FILES)
        self.assertEqual(numbers, list(range(numbers[0], numbers[-1] + 1)),
                         "gap in round numbering: %s" % numbers)

    def test_every_round_file_documents_its_defect(self):
        undocumented = []
        for path in ROUND_FILES:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            doc = ast.get_docstring(tree) or ""
            if len(doc.split()) < 15:
                undocumented.append(path.name)
        self.assertEqual(
            undocumented, [],
            "round files without a substantive docstring: %s" % undocumented)

    def test_every_round_file_follows_the_prefix_convention(self):
        for path in ROUND_FILES:
            self.assertRegex(
                path.name, r"^test_r\d{3}_[a-z0-9_]+\.py$",
                "%s breaks the naming convention" % path.name)


if __name__ == "__main__":
    unittest.main()
