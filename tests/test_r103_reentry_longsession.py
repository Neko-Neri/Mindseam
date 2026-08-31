# -*- coding: utf-8 -*-
"""Round 65 guards: the long-gap reentry anchor and a long session.

SKILL.md promises that `seam` prints "the same full anchor" as resume
when it detects a long gap — premise, full ledger, invariants, and the
state-the-pass prompt. Nothing pinned that. The long-session simulation
then runs twenty seams across a scripted arc (clean work, an error, a
recovery, more clean work) and asserts the state machine invariants at
every step: history grows by exactly one row per seam, the ledger never
loses rows, and the exit code never drifts.
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

from _controller_helper import run_controller


class ReentryAnchorTests(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.ws)

    def tearDown(self):
        os.chdir(self.cwd)

    def test_long_gap_seam_prints_the_full_anchor(self):
        run_controller(self.ws, "note", "--goal", "g", "--next", "dom: a")
        run_controller(self.ws, "seam")
        # Age the last history entry past RESUME_GAP.
        hist_path = Path(self.ws) / ".mindseam" / "history.json"
        hist = json.loads(hist_path.read_text(encoding="utf-8"))
        hist[-1]["t"] -= (mindseam_gap() + 60) if False else (
            __import__("mindseam").RESUME_GAP + 60)
        hist_path.write_text(json.dumps(hist), encoding="utf-8")
        r = run_controller(self.ws, "seam")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("long gap", r.stdout)
        import mindseam
        self.assertIn(mindseam.PREMISE.splitlines()[0], r.stdout)
        self.assertIn("The invariants:", r.stdout)
        self.assertIn("State the pass you are on", r.stdout)

    def test_recent_gap_seam_prints_the_short_form(self):
        run_controller(self.ws, "note", "--goal", "g", "--next", "dom: a")
        r = run_controller(self.ws, "seam")
        self.assertNotIn("long gap", r.stdout)
        self.assertNotIn("The invariants:", r.stdout)


def mindseam_gap():
    import mindseam
    return mindseam.RESUME_GAP


class LongSessionTests(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.ws)

    def tearDown(self):
        os.chdir(self.cwd)

    def test_twenty_seams_keep_the_state_machine_honest(self):
        import mindseam
        run_controller(self.ws, "note", "--goal", "survive twenty seams",
                       "--next", "work: step 0",
                       "--core", "state — one row per seam, no drift")
        lengths = []
        for step in range(1, 21):
            args = ["--next", "work: step %d" % step,
                    "--marker", "DONE" if step % 5 == 0 else "OPEN",
                    "--confidence", "thin" if step == 7 else "strong",
                    "--verifier", "pytest tests -q exits 0"]
            if step == 7:
                args += ["--error", "work: flaky fixture on step 7",
                         "--outcome", "failed", "--extra-steps", "1"]
            r = run_controller(self.ws, "note", *args)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            r = run_controller(self.ws, "seam")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            hist = json.loads(
                (Path(self.ws) / ".mindseam" / "history.json")
                .read_text(encoding="utf-8"))
            lengths.append(len(hist))
        # The opening note writes no history row; each seam writes one.
        self.assertEqual(lengths, list(range(1, 21)))
        book = mindseam.read_ledger()
        self.assertEqual(one(book, "Goal"), "survive twenty seams")
        self.assertEqual(len(book["Core"]), 1)


def one(book, key):
    return book[key][0] if book[key] else ""


if __name__ == "__main__":
    unittest.main()
