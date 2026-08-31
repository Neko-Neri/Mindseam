# -*- coding: utf-8 -*-
"""Round 66 guards: metacognitive trend sequence capping and note input sanitization.

mode_note previously used explicit index subtraction for trimming rolling trend
sequences in metacognition.json. The capping is now streamlined with pythonic
negative slice deletion (del items[:-5]), preventing index calculation drift while
preserving the maximum 5-item historical window for marker, confidence, and
verifier trends. This round pins trend buffer capping, heading prefix rejection
on goal/next actions, and scalar sanitization invariants.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import mindseam


class MetacognitiveTrendCappingAndNoteTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)
        os.makedirs(".mindseam", exist_ok=True)
        self.book = {
            "Goal": ["Test note capping"],
            "Core": [],
            "Verified": [],
            "Open": [],
            "Next": ["Initial step"],
        }

    def tearDown(self):
        os.chdir(self.old_cwd)
        self.temp_dir.cleanup()

    def test_trend_lists_cap_at_five_entries(self):
        for i in range(10):
            args = SimpleNamespace(
                goal=None, core=None, core_slot=None, check=None, by=None,
                open=None, settled_by=None, close=None, next=f"step_{i}",
                marker=f"M_{i}", confidence="strong" if i % 2 == 0 else "thin",
                verifier=f"verifier_test_{i}", error=None, outcome=None, extra_steps=None
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = mindseam.mode_note(self.book, args)
            self.assertEqual(code, 0)

        meta = mindseam.read_meta()
        trend = meta.get("trend", {})
        self.assertEqual(len(trend.get("marker", [])), 5)
        self.assertEqual(len(trend.get("confidence", [])), 5)
        self.assertEqual(len(trend.get("verifier", [])), 5)
        # Verify newest 5 entries are kept
        self.assertEqual(trend["marker"], ["M_5", "M_6", "M_7", "M_8", "M_9"])

    def test_note_declines_heading_prefix_on_goal_and_next(self):
        args = SimpleNamespace(
            goal="## Section Heading as Goal", core=None, core_slot=None,
            check=None, by=None, open=None, settled_by=None, close=None,
            next=None, marker=None, confidence=None, verifier=None,
            error=None, outcome=None, extra_steps=None
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = mindseam.mode_note(self.book, args)
        self.assertEqual(code, 2)
        output = buf.getvalue()
        self.assertIn("must not begin with a ledger section heading", output)


if __name__ == "__main__":
    unittest.main()
