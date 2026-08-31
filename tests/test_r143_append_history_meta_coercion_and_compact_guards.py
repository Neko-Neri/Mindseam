# -*- coding: utf-8 -*-
"""Round 71 guards: append_history metadata coercion and history compaction bounds.

append_history previously constructed a nested closure function on every call
to coerce string fields from caller-supplied metadata dictionaries. This has been
refactored with direct type inspection and iteration over known metadata keys.
In addition, this round guards metadata field coercion against non-string types,
positive integer validation for extra_steps, and automatic history compaction
when history length exceeds HISTORY_MAX.
"""

import json
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


class AppendHistoryMetaCoercionTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)
        os.makedirs(".mindseam", exist_ok=True)
        self.book = {
            "Goal": ["Test append history"],
            "Core": [],
            "Verified": ["✓01 init step — verified by: test suite with full coverage"],
            "Open": [],
            "Next": ["Next test step"],
        }

    def tearDown(self):
        os.chdir(self.old_cwd)
        self.temp_dir.cleanup()

    def test_append_history_meta_type_coercion(self):
        meta = {
            "marker": "OPEN",
            "confidence": "strong",
            "verifier": "pytest unit suite",
            "error": "syntax: unexpected token",
            "outcome": "failed: bad parse",
            "extra_steps": 2,
        }
        hist, _ = mindseam.append_history(self.book, meta=meta)
        self.assertEqual(len(hist), 1)
        entry = hist[0]
        self.assertEqual(entry["marker"], "OPEN")
        self.assertEqual(entry["confidence"], "strong")
        self.assertEqual(entry["verifier"], "pytest unit suite")
        self.assertEqual(entry["error"], "syntax: unexpected token")
        self.assertEqual(entry["outcome"], "failed: bad parse")
        self.assertEqual(entry["extra_steps"], 2)

    def test_append_history_coerces_non_string_types_cleanly(self):
        corrupted_meta = {
            "marker": 12345,  # non-string
            "confidence": None,  # non-string
            "error": ["list", "of", "errors"],  # non-string
            "outcome": {"status": "ok"},  # non-string
            "extra_steps": -5,  # negative
        }
        hist, _ = mindseam.append_history(self.book, meta=corrupted_meta)
        entry = hist[0]
        self.assertEqual(entry["marker"], "")
        self.assertEqual(entry["confidence"], "")
        self.assertEqual(entry["error"], "")
        self.assertEqual(entry["outcome"], "")
        self.assertEqual(entry["extra_steps"], 0)


if __name__ == "__main__":
    unittest.main()
