# -*- coding: utf-8 -*-
"""Round 69 guards: ledger parsing whitespace hygiene and roundtrip fidelity.

read_ledger previously performed repeated rstrip calls on pre-stripped line
headings and list item entries. The parsing has been cleaned to apply a single
whitespace normalization pass while preserving exact bullet prefix stripping
(- entry -> entry) and multi-item section lists (Core, Verified, Open).
This round pins ledger section extraction, bullet prefix normalization, and
ledger serialize/deserialize roundtrip fidelity.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import mindseam


class LedgerParsingHygieneTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)
        os.makedirs(".mindseam", exist_ok=True)

    def tearDown(self):
        os.chdir(self.old_cwd)
        self.temp_dir.cleanup()

    def test_write_and_read_ledger_roundtrip_fidelity(self):
        original = {
            "Goal": ["Solve hard multi-step theorem"],
            "Core": ["Invariant 1 — verified bounds", "Invariant 2 — no drift"],
            "Verified": ["✓01 base step — verified by: exhaustive tests across n≤10"],
            "Open": ["?01 edge case — settled by: test_edge_zero"],
            "Next": ["Run integration sweep"],
        }
        problem = mindseam.write_ledger(original)
        self.assertIsNone(problem)

        loaded = mindseam.read_ledger()
        self.assertEqual(loaded, original)

    def test_read_ledger_strips_bullet_markers_cleanly(self):
        raw_ledger = (
            "# Mindseam Workspace Ledger\n\n"
            "## Goal\nTest goal line\n\n"
            "## Core\n- Core item with bullet\nCore item without bullet\n\n"
            "## Verified\n\n"
            "## Open\n\n"
            "## Next\nTest next line\n"
        )
        with open(mindseam.LEDGER, "w", encoding="utf-8") as fh:
            fh.write(raw_ledger)

        loaded = mindseam.read_ledger()
        self.assertEqual(loaded["Goal"], ["Test goal line"])
        self.assertEqual(loaded["Core"], ["Core item with bullet", "Core item without bullet"])
        self.assertEqual(loaded["Next"], ["Test next line"])


if __name__ == "__main__":
    unittest.main()
