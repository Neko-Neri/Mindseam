# -*- coding: utf-8 -*-
"""Round 68 guards: checkpoint numbering survives the century boundary.

Verified rows are numbered "✓%02d" and open questions "?%02d" — a
format that only pads to two digits. The parser anchors on the digits,
so 100+ must round-trip: the 99th, 100th and 105th checkpoints must
carry distinct, monotonically increasing numbers that next_number
still reads back, and closing question 100 must find its target.
"""

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

from _controller_helper import run_controller


class NumberingStressTests(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.ws)
        run_controller(self.ws, "note", "--goal", "stress the numbering",
                       "--next", "dom: run")

    def tearDown(self):
        os.chdir(self.cwd)

    def test_checkpoints_cross_one_hundred_cleanly(self):
        import mindseam
        for i in range(1, 106):
            r = run_controller(self.ws, "note", "--check",
                               "step %d holds" % i,
                               "--by", "auto including empty")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        book = mindseam.read_ledger()
        self.assertEqual(len(book["Verified"]), 105)
        self.assertTrue(book["Verified"][98].startswith("✓99 "))
        self.assertTrue(book["Verified"][99].startswith("✓100 "))
        self.assertTrue(book["Verified"][104].startswith("✓105 "))
        # The next allocation reads the three-digit maximum back.
        self.assertEqual(
            mindseam.next_number(book["Verified"], "✓"), 106)

    def test_open_questions_cross_one_hundred_cleanly(self):
        import mindseam
        for i in range(1, 102):
            r = run_controller(self.ws, "note", "--open",
                               "question %d" % i,
                               "--settled-by", "test %d" % i)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        book = mindseam.read_ledger()
        self.assertEqual(len(book["Open"]), 101)
        self.assertIn("?100 question 100", " ".join(book["Open"]))
        # Close the century question against a checkpoint.
        run_controller(self.ws, "note", "--check", "it holds",
                       "--by", "auto including empty")
        r = run_controller(self.ws, "note", "--close", "100",
                           "--check", "closes the century",
                           "--by", "auto including empty")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        book = mindseam.read_ledger()
        self.assertTrue(any("closes: ?100" in row for row in book["Verified"]))


if __name__ == "__main__":
    unittest.main()
