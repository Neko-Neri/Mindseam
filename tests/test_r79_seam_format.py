# -*- coding: utf-8 -*-
"""Round 41 guards: the seam output keeps its published shape.

The seam is the controller's one recurring user-facing surface. Its
sections have an order — banner/ledger, facts, telemetry, trend,
remediation, heal, the Next-is-never-empty reminder — and two hard
contracts: every `N/100` in the Trend line set that names the session
health must agree (the round-43 banner/fact agreement, here pinned at
the seam level), and a ledger without Next must print the reminder.
These invariants were only implicit in older tests.
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


class SeamFormatTests(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.ws)
        run_controller(self.ws, "note", "--goal", "keep the seam shape",
                       "--next", "dom: first action")

    def tearDown(self):
        os.chdir(self.cwd)

    def _seams(self, count):
        for i in range(count):
            run_controller(self.ws, "note", "--next", "dom: action %d" % i,
                           "--marker", "OPEN", "--confidence", "strong",
                           "--verifier", "manual run %d including output" % i)
            r = run_controller(self.ws, "seam")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_section_order_is_stable(self):
        out = self._seams(3)
        positions = [
            out.index("── mindseam ─ seam"),
            out.index("Telemetry:"),
            out.index("Trend:"),
        ]
        self.assertEqual(positions, sorted(positions), out)

    def test_health_numbers_in_trend_agree(self):
        out = self._seams(3)
        banner = re.findall(r"score: (\d+)/100 \(", out)
        fact = re.findall(r"Health score is high \((\d+)/100\)", out)
        self.assertTrue(banner, out)
        if fact:
            self.assertEqual(set(banner), set(fact), out)

    def test_health_score_line_carries_grade(self):
        out = self._seams(3)
        self.assertRegex(out, r"score: \d+/100 \([ABCDF]\)")

    def test_next_reminder_fires_when_next_missing(self):
        # Blank the ledger Next by hand, then seam: the published
        # reminder must appear.
        import re as _re
        ledger = Path(self.ws) / ".mindseam" / "WORKSPACE.md"
        text = ledger.read_text(encoding="utf-8")
        ledger.write_text(
            _re.sub(r"## Next\n.+", "## Next\n", text),
            encoding="utf-8")
        r = run_controller(self.ws, "seam")
        self.assertIn("`Next` is never empty", r.stdout)


if __name__ == "__main__":
    unittest.main()
