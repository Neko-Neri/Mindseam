# -*- coding: utf-8 -*-
"""Round 77 guards: the controller's published voice, pinned.

Mutation batch three survived on message strings — the parts of the
controller a user actually reads:

  * the refusal prefix "NOT RECORDED:" is the promise that a declined
    edit leaves no trace in the ledger;
  * SHIFTS is the one line of moves printed under every fact block;
  * "Risk recovered across recent seams" is both a fact and the anchor
    the "recovered" remediation key matches — changing it silently
    orphaned the advice.
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
from _controller_helper import run_controller


def row(i, risk="low"):
    return {"t": 1000 + i, "next": "dom: act %d" % i, "verified": i + 1,
            "open": 0, "marker": "OPEN", "confidence": "strong",
            "verifier": "v", "risk": risk, "error": "",
            "outcome": "ok", "extra_steps": 0}


class PublishedVoiceTests(unittest.TestCase):

    def test_refusals_carry_the_not_recorded_prefix(self):
        ws = tempfile.mkdtemp()
        r = run_controller(ws, "note", "--next", "only next")
        self.assertEqual(r.returncode, 2)
        self.assertIn("NOT RECORDED:", r.stdout)

    def test_shifts_line_prints_under_fact_blocks(self):
        ws = tempfile.mkdtemp()
        cwd = os.getcwd()
        os.chdir(ws)
        try:
            run_controller(ws, "note", "--goal", "g", "--next", "dom: a")
            out = ""
            for i in range(3):
                run_controller(ws, "note", "--next", "dom: a",
                               "--marker", "OPEN", "--confidence",
                               "shaky")
                out = run_controller(ws, "seam").stdout
            self.assertIn("the moves open to you are:", out)
            self.assertIn(
                "Shift the abstraction, shift the strategy, "
                "or shift to empirics.", out)
        finally:
            os.chdir(cwd)

    def test_recovery_fact_keeps_its_published_wording(self):
        h = [row(0, "high"), row(1, "medium"), row(2, "low")]
        facts = mindseam.detect_recovery(h)
        self.assertEqual(
            facts, ["Risk recovered across recent seams: "
                    "high -> medium -> low."])

    def test_recovery_fact_still_keys_the_remediation_advice(self):
        h = [row(0, "high"), row(1, "medium"), row(2, "low")]
        facts = mindseam.observations(h)
        out = mindseam.remediation_suggestions(facts, 80)
        self.assertTrue(
            any("Risk has improved" in s for s in out),
            "the 'recovered' remediation key no longer matches: %s" % out)


if __name__ == "__main__":
    unittest.main()
