# -*- coding: utf-8 -*-
"""Round 62 capstone guards: one honest session, every layer coherent.

A full lifecycle — open the ledger, work with markers, confidence and
named verifiers, hit an error and recover from it, checkpoint, open and
close a question, seam throughout, resume, ship — must satisfy every
cross-layer contract the rounds established:

  * short-window neutrality at the start (round 12);
  * no repeated reason or fact line anywhere (round 32);
  * no phantom praise on an all-low-risk session (round 13);
  * banner, facts and telemetry agree on the health score (rounds 43+);
  * event keys consumed exactly once (round 45);
  * the ledger round-trips after the whole cycle (round 43);
  * a session that recovered and verified its work ships clean (round 17).
"""

import json
import os
import re
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

from _controller_helper import run_controller


class LifecycleCapstoneTests(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.ws)

    def tearDown(self):
        os.chdir(self.cwd)

    def _note(self, *args):
        r = run_controller(self.ws, "note", *args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def _seam(self):
        r = run_controller(self.ws, "seam")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_full_session_stays_coherent(self):
        self._note("--goal", "ship the audited module",
                   "--next", "audit: inspect the module")
        # Short-window neutrality: the first seam judges nothing.
        first = self._seam()
        self.assertIn("score: 100/100 (A)", first)

        self._note("--core", "contract — every layer agrees on one number")
        self._note("--next", "audit: run the sweep",
                   "--marker", "OPEN", "--confidence", "strong",
                   "--verifier", "pytest tests -q exits 0")
        second = self._seam()

        # An error, honestly recorded, then recovered.
        self._note("--next", "audit: rerun after failure",
                   "--error", "audit: sweep crashed on empty input",
                   "--outcome", "failed", "--extra-steps", "2")
        third = self._seam()

        self._note("--next", "audit: verify the fix",
                   "--marker", "DONE", "--confidence", "strong",
                   "--verifier", "pytest tests -q exits 0")
        self._note("--open", "does the gate cover unicode",
                   "--settled-by", "ship a CJK file through it")
        self._note("--close", "1",
                   "--check", "unicode gate holds",
                   "--by", "ship on CJK including empty input")
        self._note("--next", "ship: final register check",
                   "--marker", "PHEW", "--confidence", "strong")
        fourth = self._seam()

        resume = run_controller(self.ws, "resume")
        self.assertEqual(resume.returncode, 0)

        # 1. No line ever repeats in any seam's reason/fact output.
        for out in (second, third, fourth):
            lines = [l.strip() for l in out.splitlines()
                     if l.strip().startswith("·")]
            repeats = [l for l, c in Counter(lines).items() if c > 1]
            self.assertEqual(repeats, [], "repeated fact lines: %s" % repeats)

        # 2. No phantom praise: this session never had a high-risk step.
        for out in (second, third, fourth):
            self.assertNotIn("good risk outcome correlation", out)

        # 3. The banner score and the fact-mode score agree.
        banner = re.findall(r"score: (\d+)/100 \(", fourth)
        fact = re.findall(r"Health score is high \((\d+)/100\)", fourth)
        if fact:
            self.assertEqual(set(banner), set(fact), fourth)

        # 4. The error event was consumed exactly once.
        hist = json.loads(
            (Path(self.ws) / ".mindseam" / "history.json")
            .read_text(encoding="utf-8"))
        errors = [h.get("error") for h in hist if h.get("error")]
        self.assertEqual(len(errors), 1)

        # 5. The ledger round-trips after the whole cycle.
        sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
        import mindseam
        book = mindseam.read_ledger()
        self.assertEqual(len(book["Verified"]), 1)
        self.assertIn("closes: ?01", book["Verified"][0])
        self.assertEqual(book["Open"], [])

        # 6. A recovered, verified session ships clean.
        report = Path(self.ws) / "final.md"
        report.write_text(
            "The audit is complete: the sweep now covers all inputs,\n"
            "including empty ones, per pytest tests -q exiting 0.\n",
            encoding="utf-8")
        ship = run_controller(self.ws, "ship", str(report))
        self.assertEqual(ship.returncode, 0, ship.stdout)
        self.assertIn("clean", ship.stdout)


if __name__ == "__main__":
    unittest.main()
