# -*- coding: utf-8 -*-
"""Round 43 guards: the ledger survives its own write/read cycle.

write_ledger and read_ledger are the durability pair behind every
command. The property: what validate_book accepts, write_ledger
serialises, and read_ledger reparses must be the same book — list
sections keep every row, scalar sections keep exactly one row, and a
second write of the reparsed book is byte-stable (no churn on a
quiescent ledger).
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


class LedgerRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_ledger = mindseam.LEDGER
        self.old_dir = mindseam.LEDGER_DIR
        mindseam.LEDGER_DIR = self.tmp.name
        mindseam.LEDGER = str(Path(self.tmp.name) / "WORKSPACE.md")

    def tearDown(self):
        mindseam.LEDGER = self.old_ledger
        mindseam.LEDGER_DIR = self.old_dir
        self.tmp.cleanup()

    def _book(self):
        return {
            "Goal": ["ship the audit"],
            "Core": ["hub — fact one", "second — fact two",
                     "parked — fact three"],
            "Verified": ["✓01 holds — verified by: pytest"],
            "Open": ["?01 why — settled by: a test"],
            "Next": ["dom: act now"],
        }

    def test_round_trip_preserves_every_section(self):
        book = self._book()
        self.assertIsNone(mindseam.write_ledger(book))
        reparsed = mindseam.read_ledger()
        for key in ("Goal", "Next"):
            self.assertEqual(reparsed[key], book[key][:1])
        for key in ("Core", "Verified", "Open"):
            self.assertEqual(reparsed[key], book[key])

    def test_second_write_is_byte_stable(self):
        book = self._book()
        mindseam.write_ledger(book)
        first = Path(mindseam.LEDGER).read_text(encoding="utf-8")
        mindseam.write_ledger(mindseam.read_ledger())
        second = Path(mindseam.LEDGER).read_text(encoding="utf-8")
        self.assertEqual(first, second)

    def test_unicode_rows_survive(self):
        book = self._book()
        book["Core"].append("CJK — 验证节点 ✓ 保持")
        book["Open"].append("?02 为什么 — settled by: 测试")
        self.assertIsNone(mindseam.write_ledger(book))
        reparsed = mindseam.read_ledger()
        self.assertIn("CJK — 验证节点 ✓ 保持", reparsed["Core"])
        self.assertIn("?02 为什么 — settled by: 测试", reparsed["Open"])

    def test_scalar_sections_collapse_to_one_row(self):
        book = self._book()
        book["Goal"] = ["first goal", "second goal"]
        mindseam.write_ledger(book)
        reparsed = mindseam.read_ledger()
        self.assertEqual(reparsed["Goal"], ["first goal"])

    def test_missing_file_reads_as_empty_book(self):
        book = mindseam.read_ledger()
        self.assertEqual(
            book, {k: [] for k in mindseam.SECTIONS})


if __name__ == "__main__":
    unittest.main()
