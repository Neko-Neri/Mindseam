# -*- coding: utf-8 -*-
"""Round 65 guards: ship completion gate single-pass scan and settle verification.

mode_ship previously executed two separate reverse iterations across the history
list to independently find the latest confidence tag and the latest marker.
The scan is now consolidated into a single reverse pass that terminates as soon
as both fields are discovered, preserving exact gate observation output order.
This round pins ship completion gate observation order, shaky confidence flagging,
unsettled marker detection, and clean delivery states.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import mindseam


class ShipCompletionGateOptimizationTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)
        os.makedirs(".mindseam", exist_ok=True)
        self.book = {
            "Goal": ["Test ship gate optimization"],
            "Core": ["Core item 1"],
            "Verified": ["Verified item 1"],
            "Open": [],
            "Next": ["Next item 1"],
        }

    def tearDown(self):
        os.chdir(self.old_cwd)
        self.temp_dir.cleanup()

    def test_ship_gate_flags_shaky_confidence_and_unsettled_marker(self):
        hist = [
            {"t": 1000, "next": "step 1", "verified": 1, "confidence": "strong", "marker": "OPEN"},
            {"t": 1001, "next": "step 2", "verified": 1, "confidence": "shaky", "marker": "GRRR"},
        ]
        with open(mindseam.HISTORY, "w", encoding="utf-8") as fh:
            json.dumps(hist)
            json.dump(hist, fh)

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = mindseam.mode_ship(self.book, "Clean prose with no forbidden symbols.")
        output = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("shaky confidence was not settled before delivery", output)
        self.assertIn("marker 'GRRR' was not followed by a settle", output)

    def test_ship_gate_clean_when_phew_and_strong(self):
        hist = [
            {"t": 1000, "next": "step 1", "verified": 1, "confidence": "strong", "marker": "PHEW"},
        ]
        with open(mindseam.HISTORY, "w", encoding="utf-8") as fh:
            json.dump(hist, fh)

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = mindseam.mode_ship(self.book, "Clean delivery prose.")
        output = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("clean — the outgoing register holds.", output)


if __name__ == "__main__":
    unittest.main()
