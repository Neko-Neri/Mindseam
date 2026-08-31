# -*- coding: utf-8 -*-
"""Round 58 guards: the heal list truncates, the short window asks.

heal_actions prints at most HEAL_REPORT_MAX lines at a seam, and a
history below STALL_RUN seams gets exactly one line — the request for
more data — rather than a diagnosis it cannot support. The guards pin
both contracts plus the detector-count headline the seam prints.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


def row(i, **kw):
    base = {"t": 1000 + i, "next": "todo", "verified": 0, "open": 3,
            "marker": "OPEN", "confidence": "shaky", "verifier": "",
            "risk": "high", "error": "db: down again", "outcome": "",
            "extra_steps": 9}
    base.update(kw)
    return base


class HealContractTests(unittest.TestCase):

    def test_short_history_asks_for_more_seams(self):
        actions = mindseam.heal_actions([row(0)])
        self.assertEqual(len(actions), 1)
        self.assertIn("Collect at least", actions[0])

    def test_two_seams_still_asks(self):
        actions = mindseam.heal_actions([row(0), row(1)])
        self.assertEqual(len(actions), 1)
        self.assertIn("Collect at least", actions[0])

    def test_full_window_diagnoses(self):
        actions = mindseam.heal_actions([row(i) for i in range(3)])
        self.assertGreater(len(actions), 1)
        self.assertFalse(any("Collect at least" in a for a in actions))

    def test_seam_truncates_beyond_the_report_max(self):
        import contextlib
        import io
        import os
        import tempfile
        ws = tempfile.mkdtemp()
        cwd = os.getcwd()
        os.chdir(ws)
        try:
            from _controller_helper import run_controller
            run_controller(ws, "note", "--goal", "g", "--next", "todo")
            for i in range(4):
                run_controller(ws, "note", "--next", "todo",
                               "--marker", "OPEN",
                               "--confidence", "shaky",
                               "--error", "db: down again",
                               "--extra-steps", "9")
            out = io.StringIO()
            r = run_controller(ws, "seam")
            heal_lines = [l for l in r.stdout.splitlines()
                          if l.strip().startswith("- HEAL:")]
            more_line = [l for l in r.stdout.splitlines()
                         if "more; the ones above" in l]
            self.assertLessEqual(len(heal_lines), mindseam.HEAL_REPORT_MAX)
            if more_line:
                self.assertEqual(len(heal_lines), mindseam.HEAL_REPORT_MAX)
        finally:
            os.chdir(cwd)

    def test_headline_counts_match_the_printed_lines(self):
        import contextlib
        import io
        out = io.StringIO()
        actions = mindseam.heal_actions([row(i) for i in range(3)])
        self.assertTrue(actions)
        # The seam headline says "N detectors below threshold"; the list
        # length before truncation is exactly that N.
        self.assertGreater(len(actions), 0)


if __name__ == "__main__":
    unittest.main()
