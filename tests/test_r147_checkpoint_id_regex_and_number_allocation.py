# -*- coding: utf-8 -*-
"""Round 75 guards: precompiled checkpoint regex and monotonic sequence id allocation.

next_number previously recompiled an ad-hoc regular expression on every invocation.
The checkpoint prefix pattern (^✓(\\d+)\\b) has been hoisted into a module-level
precompiled constant (CHECKPOINT_ID_RE), eliminating regex compilation overhead during
high-frequency ledger checkpoint recording (--check). This round pins checkpoint
numbering monotonicity, custom prefix matching, and next_open_number id persistence.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import mindseam


class CheckpointIdRegexAndAllocationTests(unittest.TestCase):

    def test_next_number_with_checkpoint_prefix(self):
        rows = [
            "✓01 first step — verified by: unit tests",
            "✓02 second step — verified by: regression suite",
            "✓03 third step — verified by: all edge cases",
        ]
        num = mindseam.next_number(rows, "✓")
        self.assertEqual(num, 4)

    def test_next_number_empty_rows(self):
        self.assertEqual(mindseam.next_number([], "✓"), 1)

    def test_next_number_with_custom_prefix(self):
        rows = ["STEP-01 init", "STEP-02 process"]
        num = mindseam.next_number(rows, "STEP-")
        self.assertEqual(num, 3)

    def test_next_open_number_monotonicity(self):
        book = {
            "Open": ["?01 first open issue — settled by: fix"],
            "Verified": ["✓01 resolved — verified by: test suite — closes: ?02"],
        }
        num = mindseam.next_open_number(book)
        self.assertEqual(num, 3)


if __name__ == "__main__":
    unittest.main()
