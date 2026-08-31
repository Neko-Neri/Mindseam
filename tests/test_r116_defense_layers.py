# -*- coding: utf-8 -*-
"""Round 78 guards: batch-four survivors — layers and labels.

The fourth mutation batch survived on four contracts:

  * argparse rejects core-slot 3 with "invalid choice" before any
    business logic runs — the business refusal for slot 3 is a second,
    deeper layer, and both deserve their own witness (M33);
  * the verifier minimum length is five characters exactly (M34);
  * the thread-management gate has two halves — nexts present AND the
    detector's four-entry window satisfied; a three-entry history must
    not earn the sentinel praise through the length half alone (M39);
  * the seam's repair section is labelled "State repair:" (M41).
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


class ArgparseLayerTests(unittest.TestCase):

    def test_slot_three_is_rejected_by_argparse_itself(self):
        ws = tempfile.mkdtemp()
        r = run_controller(ws, "note", "--core", "a — b",
                           "--core-slot", "3")
        self.assertEqual(r.returncode, 2)
        combined = r.stdout + r.stderr
        self.assertIn("invalid choice", combined)
        self.assertNotIn("NOT RECORDED:", combined)


class VerifierLengthTests(unittest.TestCase):

    def test_four_character_verifier_is_refused(self):
        ws = tempfile.mkdtemp()
        r = run_controller(ws, "note", "--goal", "g", "--next", "dom: a",
                           "--verifier", "abcd")
        self.assertEqual(r.returncode, 2)
        self.assertIn("at least 5", r.stdout)

    def test_five_character_verifier_is_accepted(self):
        ws = tempfile.mkdtemp()
        r = run_controller(ws, "note", "--goal", "g", "--next", "dom: a",
                           "--verifier", "abcde")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class GateLengthHalfTests(unittest.TestCase):

    def test_three_entry_history_with_nexts_earns_no_thread_praise(self):
        h = [{"t": 1000 + i, "next": "dom: act %d" % i, "verified": i,
              "open": 0, "marker": "OPEN", "confidence": "strong",
              "verifier": "v", "risk": "low", "error": "",
              "outcome": "ok", "extra_steps": 0}
             for i in range(mindseam.STALL_RUN)]
        _, reasons = mindseam.session_health_score(h)
        self.assertFalse(
            any("high thread management" in r for r in reasons),
            "thread praise leaked through the length half of the gate: %s"
            % [r for r in reasons if "thread" in r])

    def test_four_entry_history_with_nexts_earns_thread_praise(self):
        h = [{"t": 1000 + i, "next": "dom: act %d" % i, "verified": i + 1,
              "open": 0, "marker": "OPEN", "confidence": "strong",
              "verifier": "v", "risk": "low", "error": "",
              "outcome": "ok", "extra_steps": 0}
             for i in range(mindseam.STALL_RUN + 1)]
        _, reasons = mindseam.session_health_score(h)
        self.assertTrue(
            any("high thread management" in r for r in reasons), reasons)


class RepairLabelTests(unittest.TestCase):

    def test_seam_labels_the_repair_section(self):
        ws = tempfile.mkdtemp()
        cwd = os.getcwd()
        os.chdir(ws)
        try:
            run_controller(ws, "note", "--goal", "g", "--next", "dom: a")
            run_controller(ws, "seam")
            hist_path = Path(ws) / ".mindseam" / "history.json"
            hist_path.write_text('["junk", {"t": 1}]', encoding="utf-8")
            out = run_controller(ws, "seam").stdout
            self.assertIn("State repair:", out)
        finally:
            os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
