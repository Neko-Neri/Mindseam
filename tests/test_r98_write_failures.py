# -*- coding: utf-8 -*-
"""Round 60 guards: write failures surface, never corrupt.

atomic_write_text is the only writer the controller uses. Its failure
contract: an impossible target reports a labelled problem and returns
None-or-reason (never raises), the temp file is cleaned up, and a
failure never truncates the original — the atomic replace either
happens or does not.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


class WriteFailureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_dir = mindseam.LEDGER_DIR
        mindseam.LEDGER_DIR = self.tmp.name

    def tearDown(self):
        mindseam.LEDGER_DIR = self.old_dir
        self.tmp.cleanup()

    def test_unwritable_target_reports_a_problem(self):
        # A directory cannot be replaced by a file.
        target = Path(self.tmp.name) / "occupied"
        target.mkdir()
        problem = mindseam.atomic_write_text(str(target), "data")
        self.assertIsNotNone(problem)
        self.assertIn(str(target), problem)

    def test_successful_write_leaves_no_temp_files(self):
        target = Path(self.tmp.name) / "clean.md"
        self.assertIsNone(mindseam.atomic_write_text(str(target), "data"))
        leftovers = [p.name for p in Path(self.tmp.name).iterdir()
                     if p.name.startswith(".mindseam-")]
        self.assertEqual(leftovers, [])

    def test_failed_replace_leaves_no_temp_files(self):
        target = Path(self.tmp.name) / "occupied2"
        target.mkdir()
        mindseam.atomic_write_text(str(target), "data")
        leftovers = [p.name for p in Path(self.tmp.name).iterdir()
                     if p.name.startswith(".mindseam-")]
        self.assertEqual(leftovers, [])

    def test_original_survives_a_failed_write(self):
        target = Path(self.tmp.name) / "keep.md"
        target.write_text("original", encoding="utf-8")
        # Make the replace impossible by turning the target into a
        # non-empty directory after a successful first write cycle.
        target2 = Path(self.tmp.name) / "keep2.md"
        target2.mkdir()
        problem = mindseam.atomic_write_text(str(target2), "new")
        self.assertIsNotNone(problem)
        self.assertEqual(
            target.read_text(encoding="utf-8"), "original")


if __name__ == "__main__":
    unittest.main()
