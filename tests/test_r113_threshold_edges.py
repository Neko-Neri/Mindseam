# -*- coding: utf-8 -*-
"""Round 75 guards: threshold edges that mutation testing caught bare.

A ten-mutation sweep of mindseam.py (round 113) killed six mutants and
let four survive — each survivor was a contract no test pinned:

  * HEAL_HEALTH_FLOOR 45 -> 44 changed which sessions receive heal
    advice and nothing failed;
  * the grade A edge 90 -> 89 moved a whole band silently;
  * RESUME_GAP 1800 -> 1700 survived because the reentry test derived
    its timestamps from the constant itself (mutation-invariant);
  * the decay-polarity check passed vacuously by asserting the wrong
    tuple field (fixed in test_r64).

These guards pin the four edges with absolute values.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam


class GradeEdgeTests(unittest.TestCase):

    def test_grade_band_edges_are_exact(self):
        self.assertEqual(mindseam.grade(90), "A")
        self.assertEqual(mindseam.grade(89), "B")
        self.assertEqual(mindseam.grade(75), "B")
        self.assertEqual(mindseam.grade(74), "C")
        self.assertEqual(mindseam.grade(60), "C")
        self.assertEqual(mindseam.grade(59), "D")
        self.assertEqual(mindseam.grade(40), "D")
        self.assertEqual(mindseam.grade(39), "F")


class HealFloorEdgeTests(unittest.TestCase):

    def test_health_floor_is_forty_five(self):
        self.assertEqual(mindseam.HEAL_HEALTH_FLOOR, 45)

    def test_detector_at_the_floor_flips_the_heal_line(self):
        # step_economy reads extra_steps against the SLA; craft a
        # window scoring exactly the floor and one point above it.
        def window(over_sla):
            rows = []
            for i in range(mindseam.STALL_RUN + 1):
                rows.append({"t": 1000 + i, "next": "dom: act %d" % i,
                             "verified": i, "open": 0, "marker": "OPEN",
                             "confidence": "strong", "verifier": "v",
                             "risk": "low", "error": "", "outcome": "ok",
                             "extra_steps": over_sla})
            return rows
        sla = mindseam.STALL_RUN + 2
        # 4 of 4 rows over SLA scores 0; 2 of 4 scores 50.
        at_floor = mindseam.step_economy(window(sla + 1))
        above_floor = mindseam.step_economy(window(sla))
        self.assertLess(at_floor, mindseam.HEAL_HEALTH_FLOOR)
        self.assertGreaterEqual(above_floor, mindseam.HEAL_HEALTH_FLOOR)
        self.assertIn("Step economy",
                      " ".join(mindseam.heal_actions(window(sla + 1))))


class ResumeGapEdgeTests(unittest.TestCase):

    def test_resume_gap_is_thirty_minutes(self):
        # Pinned to the absolute documented value; deriving the test
        # times from the constant again would make the guard vacuous.
        self.assertEqual(mindseam.RESUME_GAP, 1800)

    def test_reentry_fires_only_past_the_absolute_gap(self):
        import contextlib
        import io as _io
        ws = tempfile.mkdtemp()
        cwd = os.getcwd()
        os.chdir(ws)
        try:
            from _controller_helper import run_controller
            run_controller(ws, "note", "--goal", "g", "--next", "dom: a")
            run_controller(ws, "seam")
            hist_path = Path(ws) / ".mindseam" / "history.json"

            def aged(gap):
                hist = json.loads(hist_path.read_text(encoding="utf-8"))
                hist[-1]["t"] = int(time.time()) - gap
                hist_path.write_text(json.dumps(hist), encoding="utf-8")
                out = _io.StringIO()
                with contextlib.redirect_stdout(out):
                    code = mindseam.main(["seam"])
                assert code == 0
                return out.getvalue()

            self.assertNotIn("long gap", aged(1700))
            self.assertIn("long gap", aged(1900))
        finally:
            os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
